# ClipShare

A lightweight Linux application for sharing gaming clips.

Target platforms: CachyOS and Bazzite.

A functional local-first Linux desktop application for browsing gaming recordings,
trimming highlights, mixing audio and exporting H.264/AAC MP4 clips under a selected
size limit. Built with Qt6/PySide6 and FFmpeg. No Electron, accounts, backend, or
YouTube integration. **Version 0.1 is an MVP, not a fully verified release.**

## Build and run

Requires Linux, Python 3.11+, and `ffmpeg`/`ffprobe` with libx264 and AAC. Qt wheels
also need the usual desktop graphics/audio libraries. From the repository:

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/clipshare
```

Build distributable Python packages:

```sh
.venv/bin/pip install build
.venv/bin/python -m build
```

Run automated checks (FFmpeg must be on PATH):

```sh
.venv/bin/pip install pytest
QT_QPA_PLATFORM=offscreen QT_AUDIO_BACKEND=pulseaudio .venv/bin/python -m pytest -q
```

In a headless environment with a read-only home, also set `XDG_CONFIG_HOME`,
`XDG_CACHE_HOME` and `XDG_DATA_HOME` to writable directories. Offscreen testing
cannot verify Wayland drag-and-drop or actual speaker output.

## Using ClipShare

1. Add one or more recording folders. MP4, MKV, MOV and WebM files are discovered
   recursively. New/changed files are probed after a quiet period.
2. Select a thumbnail, preview, and set trim in/out values or drag the two timeline
   sliders. Seeking and play/pause use the embedded Qt video player.
3. Check audio tracks and gain. Exclude any already-mixed duplicate track. Preview
   mix renders exactly the selected tracks/range before playing it.
4. Choose 10/25/50/100 MB or enter a custom limit. Compress for Discord, or export
   a quality clip without a size limit. Originals are never used as output paths.
5. Drag the exported file into Discord, copy it, or open its folder. Exports persist
   after closing the app. Default location: `~/Videos/ClipShare` (configurable).
6. Optional Catbox buttons upload either the original unchanged or the last export.
   Successful real responses are copied to the clipboard and saved in history.
   **Catbox's current policies and live operation remain unverified**; read
   [provider research/status](docs/PROVIDERS.md) before use.

Jobs run in background workers with progress and cancellation. Only one interactive
export/upload runs at a time. Hardware choices are optional; software is the default.
Settings and upload history use XDG directories. Diagnostics are in
`$XDG_DATA_HOME/clipshare/clipshare.log` (default `~/.local/share/clipshare`).

## CachyOS / Arch

For development or direct native use:

```sh
sudo pacman -S --needed python python-pip ffmpeg
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/clipshare
```

A local-source PKGBUILD is supplied. From the repository root:

```sh
tar --exclude=.git --exclude=.venv --exclude=dist --exclude=build \
    --exclude=packaging/vendor --exclude='*.tar.gz' \
    --transform='s,^\.,clipshare-0.1.0,' -czf /tmp/clipshare-0.1.0.tar.gz .
cp /tmp/clipshare-0.1.0.tar.gz packaging/
cd packaging
makepkg -si
```

Arch packages supply PySide6; Python package version metadata is primarily for pip.
This PKGBUILD has not been built on Arch. A published release should replace its
local-source `SKIP` hash with a release checksum.

## Flatpak / CachyOS / Bazzite

The intended end-user installer is `ClipShare.flatpak` from
[GitHub Releases](https://github.com/PhoxyYT/ClipShare/releases), opened with Discover
or installed using `flatpak install --user ./ClipShare.flatpak`. No host Python,
virtual environment or FFmpeg is needed. Only download releases that actually
contain a bundle; a source ZIP is not an installer.

See [installation, update, uninstall and troubleshooting](docs/INSTALL.md) and
[build/release maintenance and verification status](docs/FLATPAK.md).

For developers with Flatpak and flatpak-builder installed:

```sh
bash packaging/build-flatpak.sh
```

This builds the checksum-locked x86_64 manifest, creates `dist/ClipShare.flatpak`,
installs that bundle and tests the installed application. The new Flatpak workflow
runs the same pipeline and attaches successful builds to published GitHub Releases.
**The Flatpak has been built, installed and smoke-tested successfully in
[GitHub Actions](https://github.com/PhoxyYT/ClipShare/actions/runs/41216654657).**
For the current test build, download [ClipShare-flatpak-x86_64](https://github.com/PhoxyYT/ClipShare/actions/runs/41216654657/artifacts/13049215511)
while signed into GitHub, extract the ZIP and open `ClipShare.flatpak` with Discover.
The artifact also includes checksums, the smoke-test report and build inputs.
Actions artifacts expire after 14 days; release builds will attach permanent
release assets when a GitHub Release is published. Real CachyOS/Bazzite desktop
compatibility and hardware acceleration are not yet verified.

## Verification and remaining scope

See [test results and platform checklist](docs/TESTING.md) and
[architecture and processing details](docs/ARCHITECTURE.md).

Known limitations: no named audio profile collection (one saved default exists),
translations, light-theme selector, desktop autostart, export queue, waveform,
manual resolution/FPS controls, general remux optimization, or cache size manager.
Mix preview creates a rendered cache file rather than a real-time mixer. Recording
completion detection uses unchanged size/mtime, which cannot prove that a paused
recorder has finished. Metadata may become stale for unusual edits preserving both
size and mtime. Provider retention is never guaranteed. Real desktop integration,
hardware, long-session performance and distribution packaging need further testing.
