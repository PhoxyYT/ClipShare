# Flatpak build and release maintenance

The existing Qt/PySide application is retained. The manifest builds CPython,
x264, FFmpeg and the Kerberos/GSSAPI libraries needed by QtNetwork/QtMultimedia
from checksum-locked upstream archives and installs exact
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
published releases. It requires the full application regression workflow to pass, validates desktop
metadata, runs the complete Flatpak build
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

## Verified packaging status — 31 October 2026

[Run 41216654657](https://github.com/PhoxyYT/ClipShare/actions/runs/41216654657) passed for source commit `e9b137c` on GitHub's
Ubuntu 24.04 x86_64 runner. The workflow passed the application regression suite,
validated desktop/AppStream metadata, built/exported the Flatpak, installed the
actual bundle, and ran `clipshare.selftest` under Freedesktop Platform 25.08.
The smoke test checks desktop-plugin shared libraries (Wayland, X11 and portal),
Qt window construction, real H.264/AAC encode/trim/mix, output size, unchanged
original bytes and a valid decoded QtMultimedia frame. It does not test audible
speaker output or desktop interaction.

The [uploaded artifact](https://github.com/PhoxyYT/ClipShare/actions/runs/41216654657/artifacts/13049215511) contains `ClipShare.flatpak`, checksums,
`flatpak-selftest.json` and `ClipShare-build-inputs.tar.gz`. GitHub reports the
combined artifact as 501 MB, digest
`sha256:18d6ed0c5764767f51dbc765923cd5784d20ec5b4c0b9d306f554494f4d62a85`.
That is the combined Actions artifact digest, not the Flatpak file checksum;
the latter is provided in the downloaded checksum file. Actions downloads require
GitHub sign-in and expire after 14 days. Release publishing is configured but has
not been exercised by creating a release during this task.

Two errors were found and fixed: QtMultimedia required the missing GSSAPI library,
so Kerberos is now bundled; appending a long wheel filename to Git's ustar archive
failed, so release inputs now use a fresh PAX archive. All 15 input files were
round-trip checked against their recorded hashes locally. Successful module caches
are saved before release archive assembly to avoid rebuilding after artifact errors.

In the local Debian development container, the 18 tests, built-wheel smoke test,
Kerberos source build and metadata/source verification passed. Local Flatpak
execution is still blocked by the environment's Flathub network policy; the
actual Flatpak build/installation/smoke-test evidence is from GitHub Actions.
GPU encoding, audible playback, Wayland/Discord drag-and-drop, persistent directory
portal access and real CachyOS/Bazzite desktop behavior remain unverified.

FFmpeg autodetection is disabled so an optional SDK-only library cannot silently
become an undeclared runtime dependency. The software libx264 encoder is explicitly
enabled; AAC and common input decoders are built into FFmpeg. Hardware encoders
must be added with their headers/runtime extensions and tested explicitly later.
