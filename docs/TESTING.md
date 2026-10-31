# Verification — 31 October 2026

Initial MVP environment: Debian 13 container, Python 3.12, FFmpeg/FFprobe 7.1.5, Qt/PySide
6.8.3. No real desktop session, audio output device, GPU, Flatpak tools, CachyOS,
or Bazzite installation was available.

Automated checks cover:

- Real FFmpeg two-pass encoding, ffprobe validation, decimal-byte output limit.
- Trimming, output duration, audio/video start-time alignment.
- Multiple mono audio tracks with 44.1/48 kHz sample rates plus a silent track.
- Spectral measurement proving both 440 Hz and 880 Hz selected inputs contribute
  to the output, with no corresponding unrelated 660 Hz tone.
- Selection of individual tracks and retention of separate streams when mixing
  is disabled; valid video-only output when no tracks are selected.
- 1080p60 and 1440p60 sources reduced to small budgets.
- A 65-second variable-frame-rate source trimmed across its rate transition.
- Software fallback after an injected hardware encoder failure.
- Invalid files, invalid ranges/budgets, cancellation and partial-file cleanup.
- Original file hash unchanged; compatible no-transform copy byte-identical.
- Actual filesystem events: recursive discovery, JPEG/JSON cache, rename, delete.
- Offscreen Qt window construction, settings persistence and disabled file drag
  before an export exists.
- Actual HTTP multipart requests against a local mock server, neutral upload
  filename, cancellation, and rejection of untrusted sharing URLs.

A separate offscreen player check loaded and advanced through an H.264/AAC fixture
(position reached 1741 ms without a player error). Qt reported no audio device;
this demonstrates the playback pipeline runs, not audible output or reliable
onscreen GPU rendering. A window capture was inspected for layout. The offscreen
backend does not capture QVideoWidget's rendered surface reliably.

Python wheel and source distribution were built successfully. Flatpak input
preparation downloaded source archives and wheels and recorded archive SHA-256s;
the Arch package has NOT been built. Subsequent packaging work successfully built,
installed and smoke-tested the Flatpak in [GitHub Actions](https://github.com/PhoxyYT/ClipShare/actions/runs/41216654657).
See [the packaging verification record](FLATPAK.md) for exact scope and artifacts.

## Required platform acceptance checks

- CachyOS/KDE Wayland and Bazzite/KDE: launch, native folder dialog, playback with
  audible selected mix, long-running recording discovery, settings and shutdown.
- Real OBS files containing a premixed track: exclude that track, listen for
  duplicated voices, check delayed stream start times and sync throughout a long
  recording. Synthetic frequency tests do not replace this listening check.
- AMD/Intel VA-API and NVIDIA NVENC: real device export, permissions, driver errors,
  quality/size at low bitrates. QSV and multi-GPU configurations need device tests.
- Force a real oversized output to exercise bitrate retries end-to-end. The tests
  verify bounded final size, but do not currently force every retry branch.
- Build/install Flatpak, validate AppStream, confirm bundled FFmpeg codecs and Qt
  plugins, test persistent folder portal access and watching after restart.
- Drag a completed export into native Discord, browser Discord and Flatpak Discord
  under Wayland and X11. Verify the receiving app can read the URI. Flatpak Discord
  may need access to the output directory; use its file picker/portal or grant only
  that directory. Copy file/path and Open output folder are fallbacks, not proof
  that cross-sandbox drag-and-drop works.
- Check Catbox's current API, terms, limits, retention and service restrictions;
  upload an explicitly approved expendable fixture and confirm its real link and
  browser playback. No live upload was attempted or reported successful.
- Measure memory, idle CPU, large-library behavior and encode throughput on target
  hardware. No performance figures are claimed.

The broader project definition of done remains incomplete until those platform
checks and the missing settings/features listed in README are addressed.
