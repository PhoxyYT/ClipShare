#!/usr/bin/env bash
# Run from any directory. Installs build dependencies per-user, never system-wide.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
app_id=io.github.clipshare.ClipShare
manifest=packaging/io.github.clipshare.ClipShare.json
for tool in flatpak flatpak-builder; do
    command -v "$tool" >/dev/null || { echo "Required build tool missing: $tool" >&2; exit 1; }
done
[[ $(uname -m) == x86_64 ]] || { echo 'This manifest currently supports x86_64 only.' >&2; exit 1; }
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user --noninteractive flathub org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08
mkdir -p dist
flatpak-builder --user --force-clean --disable-rofiles-fuse --repo=flatpak-repo \
    flatpak-build "$manifest"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
    flatpak-repo dist/ClipShare.flatpak "$app_id" stable
# Install the actual distributable and run against Platform (not the SDK).
flatpak install --user --noninteractive --or-update dist/ClipShare.flatpak
flatpak run --env=QT_QPA_PLATFORM=offscreen --env=QT_AUDIO_BACKEND=pulseaudio \
    --command=python3 "$app_id" -m clipshare.selftest | tee dist/flatpak-selftest.json
(cd dist && sha256sum ClipShare.flatpak > ClipShare.flatpak.sha256)
echo 'Built and tested dist/ClipShare.flatpak'
