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

## Flatpak / Bazzite

A Flatpak manifest, source preparation script, desktop entry, AppStream metadata
and SVG icon are included. The manifest bundles CPython, x264, FFmpeg and Qt wheels;
it does not depend on host FFmpeg or changes to immutable system partitions.
The current recipe targets **x86_64**. It has **not been built or installed** in this
environment, so Flatpak buildability and Bazzite compatibility are not marked done.
Build on a Linux development machine with Flatpak/flatpak-builder and Flathub:

```sh
flatpak install --user flathub org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08
.venv/bin/python packaging/prepare-flatpak.py
flatpak-builder --user --install --force-clean flatpak-build packaging/io.github.clipshare.ClipShare.json
flatpak run io.github.clipshare.ClipShare
```

To produce a transferable bundle, use `flatpak-builder --repo=repo --force-clean
flatpak-build packaging/io.github.clipshare.ClipShare.json`, then:

```sh
flatpak build-bundle repo ClipShare.flatpak io.github.clipshare.ClipShare
```

On Bazzite, install the resulting tested bundle per user, without system layering:

```sh
flatpak install --user ./ClipShare.flatpak
flatpak run io.github.clipshare.ClipShare
```

The preparation script downloads wheels and source archives before the sandboxed
build, records archive hashes, and keeps inputs in ignored `packaging/vendor/`.
Retain those inputs for reproducibility; transitive wheels and the x264 stable
branch are resolved when preparing a fresh vendor directory. This is a developer
recipe, not a published/reproducible Flathub release yet. Bundled FFmpeg/x264 are
GPL components; redistribution must meet their corresponding-source obligations.

Permissions: Wayland, fallback X11, audio, DRI, optional-hosting network, and Videos
folder access; no unrestricted home access. For custom recording folders, grant
only that folder if the file portal doesn't provide persistent recursive access:

```sh
flatpak override --user --filesystem="$HOME/Videoklip/Clips:ro" io.github.clipshare.ClipShare
```

Similarly grant write access to a custom output folder. Qt's file dialog uses
platform integration where available; persistent portal directory watching still
needs KDE testing. The baseline Flatpak FFmpeg recipe is software-focused; native
FFmpeg installs can use NVENC, VA-API and QSV when built with those APIs and supplied
with working drivers. Flatpak GPU encoding has not been validated.

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
