# Flatpak build and release maintenance

The existing Qt/PySide application is retained. The manifest builds CPython,
x264 and FFmpeg from checksum-locked upstream archives and installs exact
checksum-locked Python wheels offline. QtMultimedia and its FFmpeg playback
libraries come from PySide6 Essentials/Addons; no host Qt or FFmpeg is used.
The application FFmpeg command and Qt's playback FFmpeg libraries are separate.
The manifest copies only application source, project metadata and desktop assets,
not the entire developer checkout, virtual environment or credentials.

## Build, install and test

On a Linux build machine with Flatpak, flatpak-builder, a session D-Bus and working
unprivileged user namespaces:

```sh
bash packaging/build-flatpak.sh
```

The script installs Freedesktop Platform/SDK 25.08 per-user, downloads pinned
sources, builds, exports `dist/ClipShare.flatpak`, installs that exact bundle, then
runs `clipshare.selftest` using the Platform. It exits unsuccessfully if any stage
fails. Success produces `dist/ClipShare.flatpak.sha256` and
`dist/flatpak-selftest.json`. No Python/venv setup on the receiving desktop is needed.

The first build is large and needs network access to dl.flathub.org, GitHub source
archives and files.pythonhosted.org. Subsequent builds reuse flatpak-builder's
cache. The application bundle carries the Flathub runtime-repository hint. The
branch is `stable`; the application ID remains unchanged to preserve MVP settings.
Only x86_64 wheels are currently supported. Aarch64 needs its own dependency lock.

## CI and releases

`.github/workflows/test.yml` runs the application test suite. The additional
`flatpak.yml` workflow runs on PRs, main/codex branch pushes, manual dispatch and
published releases. It validates desktop metadata, runs the complete Flatpak build
and installed-bundle smoke test, then makes the installer/checksums/test report and
exact build inputs available as a workflow artifact. A separate job with narrowly
scoped `contents: write` permission uploads those files to GitHub Releases **only
on a release event and only after the build succeeds**. Fork PRs cannot publish.
Existing assets are not overwritten silently. CI does not create releases itself.

Merge the workflow into main, update the application and AppStream versions for a
release, create a tag from that commit, and publish a GitHub Release for that tag.
The workflow must exist in the tagged commit. Wait for its successful run and
confirm the `ClipShare.flatpak` asset appears before directing users to download.
Release creation, runtime validation on CachyOS/Bazzite, and an update repository
remain maintainer steps. A release label alone does not mean its build succeeded.

## Distribution inputs and licenses

The application is MIT; x264 and the enabled FFmpeg build include GPL components.
`prepare-flatpak.py` now downloads and verifies the already-pinned third-party
inputs without editing the manifest. The release archive contains application
source/build scripts, exact x264/FFmpeg/CPython source archives and Python wheels.
It is named `ClipShare-build-inputs.tar.gz`, not a claim that binary Qt wheels are
source archives. Preserve upstream notices and check Qt/PySide LGPL/GPL obligations
and corresponding Qt source availability before public distribution. Qt/PySide
remain dynamically linked. Freedesktop runtime licensing is managed separately.

## Local validation status

Flatpak 1.16.6 and flatpak-builder 1.4.4 were obtained in the Debian development
container. The manifest loads in flatpak-builder; its download-only run successfully fetched
and checksum-verified all declared archives and wheels. Desktop-file and AppStream
validation pass, and the 18 regression tests pass. The standalone installed-
package smoke test passes natively (real H.264/AAC encode, trim, mix, bounded size,
unchanged original, window launch and a decoded 320×180 QtMultimedia frame).

The full build command has been attempted but **cannot yet download Flathub's
runtime repository**: the environment proxy denies dl.flathub.org. The requested
network allowlist edit is saved but needs environment publication. Therefore no
local Flatpak build, installed-bundle launch or installable bundle is claimed yet.
The new GitHub workflow has not yet been observed completing. This status must be
updated with actual build evidence once access is active; a manifest parse is not
a successful build. GPU encoding, audible playback, Wayland/Discord drag-and-drop,
and CachyOS/Bazzite desktop behavior remain unverified on real hardware.

FFmpeg autodetection is disabled so an optional SDK-only library cannot silently
become an undeclared runtime dependency. The software libx264 encoder is explicitly
enabled; AAC and common input decoders are built into FFmpeg. Hardware encoders
must be added with their headers/runtime extensions and tested explicitly later.
