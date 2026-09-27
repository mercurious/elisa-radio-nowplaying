# elisa-radio-nowplaying

Make KDE's **Elisa** music player on Fedora show the current artist/track for
internet radio (tested with [SomaFM](https://somafm.com)), both in Elisa itself
and in the Plasma media widget / lock screen — and play it at the source's
native sample rate with no resampling or digital volume scaling.

Built and tested on Fedora 44 (Asahi Remix, aarch64), Elisa 26.08.1, VLC 3.0.23.

## Why stock Elisa doesn't show it

Three separate problems stack up:

1. **Fedora builds Elisa with the Qt Multimedia backend.** Only Elisa's libVLC
   backend reads a stream's ICY "now playing" metadata
   (`src/audiowrapper_libvlc.cpp`); the Qt Multimedia wrapper ignores it
   entirely. There is no setting for this — it's a build-time choice, so the
   package has to be rebuilt against `libvlc`.
2. **VLC 3 only reads ICY titles over plain `http://`.** Its HTTPS access
   module drops the metadata, so `https://ice1.somafm.com/...` plays but never
   reports a track. SomaFM serves the same streams over `http://`.
3. **Elisa's MPRIS interface doesn't refresh on in-place title changes.** Even
   with libVLC, Elisa's own header updates but the Plasma widget keeps showing
   the station name, because MPRIS metadata is only rebuilt when the track or
   its duration changes. `elisa-mpris-radio-metadata.patch` fixes that for radio
   entries only.

Bonus: SomaFM URLs of the form `groovesalad-256.mp3` return 404; the working
form is `groovesalad-256-mp3`.

## Audio quality

Once Elisa uses libVLC, three more things keep audio from reaching the DAC untouched:

1. **Everything gets resampled to 48 kHz.** VLC's native PipeWire output doesn't
   tell PipeWire the stream's sample rate, so a 44.1 kHz stream (SomaFM, CDs) is
   resampled to the graph's default 48 kHz. VLC's PulseAudio output does
   (`node.rate = 1/44100` via pipewire-pulse), and since PipeWire allows
   44.1–192 kHz on Asahi, the DAC then switches to the track's native rate.
   `elisa-libvlc-pulse-output.patch` makes Elisa pick the Pulse output.
2. **The fallback resampler is mid-quality.** When resampling can't be avoided
   (another app holds the output at a different rate), PipeWire uses quality 4
   of 10. `pipewire/pipewire-pulse.conf.d/60-hifi-resample.conf` raises it to 10.
3. **Elisa's volume slider is a digital gain.** Anything below 100% scales
   samples in software. Leave Elisa at 100% and use the system volume, which on
   Asahi's headphone output is the DAC's own hardware volume.

Check the whole chain while playing:

```bash
pw-top -b -n 2 | grep -E 'Headphones|Elisa'
```

The DAC and Elisa should show the same rate (e.g. `44100`) and Elisa's `ERR`
count should stay at 0. `wpctl inspect <sink-id>` should show `softVolumes` of
1.0 (volume done in hardware).

## What's here

| File | Purpose |
| --- | --- |
| `elisa-player.spec` | Fedora's spec with libVLC enabled, both patches, and a `.vlc` release tag |
| `fedora-spec.diff` | The same changes as a diff against Fedora's `26.08.1-1` spec, for porting to new versions |
| `elisa-mpris-radio-metadata.patch` | Elisa patch: push radio title/artist changes to MPRIS |
| `elisa-libvlc-pulse-output.patch` | Elisa patch: use VLC's Pulse output so playback runs at the native sample rate |
| `pipewire/pipewire-pulse.conf.d/60-hifi-resample.conf` | PipeWire drop-in: highest-quality resampler for the cases that still need one |
| `build.sh` | Fetches the Fedora source RPM if needed and builds into `~/rpmbuild` |
| `install.sh` | Installs the built RPM and version-locks it |
| `fix-somafm-urls.py` | Rewrites SomaFM entries in Elisa's radio list to working `http://` URLs (backs up the DB) |

## Usage

One-time build dependencies:

```bash
sudo dnf install rpm-build 'pkgconfig(libvlc)' && sudo dnf builddep elisa-player
```

Build, install, and fix the station URLs (quit Elisa first):

```bash
./build.sh && ./install.sh && ./fix-somafm-urls.py
```

Install the resampler setting:

```bash
install -Dm644 -t ~/.config/pipewire/pipewire-pulse.conf.d pipewire/pipewire-pulse.conf.d/60-hifi-resample.conf && systemctl --user restart pipewire-pulse
```

Then start Elisa, set its volume to 100%, and play a station from **Radios**.
Streams opened as plain URLs (command line, MPRIS `OpenUri`) aren't treated as
radios and won't show track changes.

## When Fedora ships a new Elisa

`install.sh` version-locks the package, so `dnf upgrade` won't replace it. To
move to a new version:

1. Update `Version:` and reset `Release:` to `1.vlc%{?dist}` in
   `elisa-player.spec` — or take Fedora's new spec and apply `fedora-spec.diff`
   to it.
2. `./build.sh && ./install.sh`
3. If a patch no longer applies, check `src/mpris2/mediaplayer2player.cpp` or
   `src/audiowrapper_libvlc.cpp` upstream; the fix may have landed or need refreshing.

## Undo

```bash
sudo dnf versionlock delete elisa-player && sudo dnf distro-sync --allow-vendor-change elisa-player
```

```bash
rm ~/.config/pipewire/pipewire-pulse.conf.d/60-hifi-resample.conf && systemctl --user restart pipewire-pulse
```

Radio URL backups are at `~/.local/share/elisa/elisaDatabase.db.bak-<date>`.

## Notes

- Plasma shows SomaFM tracks as title = `Artist - Song` (SomaFM sends one
  string) and artist = the station's description.
- Non-SomaFM stations saved with `https://` URLs have the same VLC limitation;
  switch them to `http://` if the station supports it.
- Building needs ~1.3 GB RAM at 4 jobs; `build.sh` caps parallelism for 8 GB machines.

## License

LGPL-3.0-or-later, the same as Elisa — see [`COPYING.LESSER`](COPYING.LESSER)
and the GPL-3.0 text it builds on in [`COPYING`](COPYING).

`elisa-player.spec` and `fedora-spec.diff` are derived from Fedora's
[elisa-player packaging](https://src.fedoraproject.org/rpms/elisa-player),
whose spec files are MIT-licensed under the Fedora Project Contributor Agreement.
