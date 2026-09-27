#!/bin/bash
# Rebuild Fedora's elisa-player with the libVLC backend and the MPRIS radio patch.
# Fetches the matching Fedora source RPM into ~/rpmbuild if needed, then builds
# with this repo's spec and patch. Output: ~/rpmbuild/RPMS/<arch>/elisa-player-*.vlc.*.rpm
#
# Build deps (once): sudo dnf install rpm-build 'pkgconfig(libvlc)' && sudo dnf builddep elisa-player
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
top=$HOME/rpmbuild
version=$(rpmspec -q --srpm --qf '%{version}\n' "$here/elisa-player.spec")

if [ ! -f "$top/SOURCES/elisa-$version.tar.xz" ]; then
    mkdir -p "$top/SRPMS"
    (cd "$top/SRPMS" && dnf download --srpm --repo=fedora-source --repo=updates-source "elisa-player-$version")
    srpm=$(ls -t "$top"/SRPMS/elisa-player-"$version"-*.src.rpm | head -1)
    rpm -K "$srpm"
    rpm -i "$srpm"
fi

install -Dm644 "$here/elisa-player.spec" "$top/SPECS/elisa-player.spec"
install -Dm644 "$here/elisa-mpris-radio-metadata.patch" "$top/SOURCES/elisa-mpris-radio-metadata.patch"

# capped at 4 compile jobs: an 8 GB machine runs out of memory at -j8
exec rpmbuild -bb --define "_smp_ncpus_max 4" "$top/SPECS/elisa-player.spec"
