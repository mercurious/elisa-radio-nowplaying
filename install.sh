#!/bin/bash
# Install the RPM that build.sh produced and version-lock it so a stock Fedora
# elisa-player update can't silently replace it.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
nvr=$(rpmspec -q --srpm --qf '%{name}-%{version}-%{release}\n' "$here/elisa-player.spec")
rpm=$HOME/rpmbuild/RPMS/$(uname -m)/$nvr.$(uname -m).rpm

[ -f "$rpm" ] || { echo "Not built yet: $rpm (run ./build.sh)" >&2; exit 1; }

sudo dnf versionlock delete elisa-player >/dev/null 2>&1 || true
# a rebuild keeps the same name-version-release, which `dnf install` skips as "already installed";
# local builds have no vendor, so dnf5 needs --allow-vendor-change to replace Fedora's package
if rpm -q "$nvr.$(uname -m)" >/dev/null 2>&1; then
    sudo dnf reinstall -y --allow-vendor-change "$rpm"
else
    sudo dnf install -y --allow-vendor-change "$rpm"
fi
sudo dnf versionlock add elisa-player
echo "Installed $nvr. Restart Elisa to use it."
