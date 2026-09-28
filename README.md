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

### Lossless radio: Radio Paradise

SomaFM tops out at 256 kbps MP3. [Radio Paradise](https://radioparadise.com)
streams lossless FLAC (16-bit/44.1 kHz). Use their **`flacm`** streams: the
plain `flac` streams carry no track info, while `flacm` adds ICY now-playing
metadata. Main, Mellow, Rock, and Global Mix have `flacm` variants; Serenity
doesn't.

**VLC 3 can't play them directly.** Radio Paradise sends Ogg FLAC, and VLC 3
can't play *any* live Ogg FLAC over HTTP — the FLAC decoder hits
`buffer deadlock prevented` and no audio ever comes out (the ICY titles still
show, which makes it look like it's playing). Rebasing the Ogg timestamps or
remuxing doesn't help; a *native* FLAC stream plays fine.

`rp-flac-relay/` is a small localhost relay that bridges the gap: it fetches the
`flacm` stream, strips the ICY metadata, has ffmpeg repackage the Ogg FLAC as
native FLAC, and serves it on `127.0.0.1:8394` with the titles re-inserted.
FLAC→FLAC is lossless — the decoded PCM is bit-identical to Radio Paradise's —
and costs about 1% of a CPU core. Install it as a user service, then add the
stations (quit Elisa first):

```bash
install -Dm755 rp-flac-relay/rp-flac-relay ~/.local/bin/rp-flac-relay
install -Dm644 rp-flac-relay/rp-flac-relay.service ~/.config/systemd/user/rp-flac-relay.service
systemctl --user daemon-reload && systemctl --user enable --now rp-flac-relay
./add-radio-paradise-flac.py
```

Elisa asks VLC for a 10 s network buffer on every stream, so any station takes
about 10 s to start; the relay itself adds ~0.4 s.

### Stuttering / silent radio: WNYC

WNYC's stream URLs (from [wnyc.org/live](https://wnyc.org/live)) don't have the
SomaFM problems, but two new ones:

1. **The MP3 stream stutters.** WNYC's edge CDN delivers audio in bursts -- gaps
   up to ~1.3s between reads, measured directly -- instead of a steady trickle.
   VLC 3's jitter buffer can't absorb that, so playback repeatedly flushes and
   drops to silence for as long as it plays, even with Elisa's 10s network
   buffer.
2. **The AAC stream never plays at all.** It's HE-AACv2 with implicit SBR/PS
   signaling (the ADTS header claims mono; the real decoded audio is stereo via
   parametric stereo). Both of VLC 3's AAC decoders (`faad`, `avcodec`)
   miscalculate the playback clock for that signaling style and never recover;
   `fdk-aac` is compiled into this VLC build only as an encoder, so there's no
   better decoder to switch to. Not fixable short of a newer VLC -- the AAC
   entry has to go.

`wnyc-relay/` fixes the MP3 stream: it reads the upstream audio into a buffer as
fast as it arrives (bursts and all), then drips it out to Elisa at the stream's
own bitrate -- a few seconds of prebuffer absorb the bursts, so VLC only ever
sees a steady trickle. Install it as a user service, then update the station
(quit Elisa first):

```bash
install -Dm755 wnyc-relay/wnyc-relay ~/.local/bin/wnyc-relay
install -Dm644 wnyc-relay/wnyc-relay.service ~/.config/systemd/user/wnyc-relay.service
systemctl --user daemon-reload && systemctl --user enable --now wnyc-relay
./add-wnyc.py
```

`add-wnyc.py` points the WNYC MP3 entry at the relay and removes the AAC entry.

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
| `add-radio-paradise-flac.py` | Adds Radio Paradise's lossless FLAC channels, with track info, to Elisa's radio list (via the relay) |
| `rp-flac-relay/` | Localhost relay + systemd user unit that makes Radio Paradise FLAC playable in VLC 3 |
| `add-wnyc.py` | Points Elisa's WNYC MP3 entry at the relay and removes the unfixable AAC entry |
| `wnyc-relay/` | Localhost relay + systemd user unit that paces WNYC's bursty stream so VLC 3 doesn't stutter |

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

```bash
systemctl --user disable --now rp-flac-relay && rm ~/.config/systemd/user/rp-flac-relay.service ~/.local/bin/rp-flac-relay
```

```bash
systemctl --user disable --now wnyc-relay && rm ~/.config/systemd/user/wnyc-relay.service ~/.local/bin/wnyc-relay
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
