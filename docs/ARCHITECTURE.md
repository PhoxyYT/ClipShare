# Engineering decisions

Qt6 Widgets with PySide6 is used instead of Rust bindings or Kirigami. Qt provides
native multimedia, file dialogs, desktop clipboard/file URLs and Wayland drag
support, and integrates well with KDE. Python reduces binding/build complexity;
FFmpeg does the expensive processing outside the Python process. GTK4/libadwaita
would add GNOME styling conventions and dependencies on the KDE target. A Rust
core can replace the small media module later, but this implementation is Python,
not a Rust project. PySide Essentials/Addons are used without WebEngine/Electron.

- `media.py`: subprocess lifecycle, ffprobe, normalized audio mix, bitrate budgets,
  two-pass H.264 encoding, hardware attempts with software fallback, size validation,
  source-change checks and atomic no-overwrite publication.
- `library.py`: recursive inotify-backed watchdog monitoring, initial scan in a
  background thread, two unchanged stat observations separated by two seconds,
  bounded probe retries, signature-based JSON/JPEG cache.
- `hosting.py`: provider protocol, streamed multipart HTTP and strict URL validation.
- `app.py`: Qt widgets, background QRunnable processing, player and user settings.

Files remain in the chosen output folder. Work files live in an export-specific
hidden directory on the same filesystem and are removed on errors/cancellation.
Publication uses an atomic hard link from the completed temporary file to a unique
output filename; this requires a filesystem supporting hard links (normal Linux
filesystems do). The untouched copy path uses independent bytes, not a link to the
original. FAT/exFAT export folders are not currently supported for publication.

Audio conversion uses 48 kHz stereo, per-track gain, normalized `amix`, and a
latency-compensated limiter. Selecting an existing full mix together with its
constituent tracks duplicates sound: the app warns and offers individual switches;
it cannot reliably infer recording routing. All tracks are selected on first use;
saved defaults apply by ordinal position, so verify profiles after changing OBS
routing. Disabling mixing retains separate selected AAC streams; Discord may play
only one. Mix preview renders the selected section before playback, which takes
encoding time. Source playback itself uses one stream.

Discord budgets use decimal MB, 7% safety headroom and 128 kbit/s per output audio
stream. Software encoding is two-pass; up to three attempts adjust the video rate.
Low budgets reduce height to 720/480/360 and FPS to at most 30; normal compression
caps at 1080/60 without increasing source frame rate. Quality export preserves
source dimensions/frame timing, uses x264 CRF 18, and is lossy when processing is
needed. Exact, untouched compatible MP4s are copied byte-for-byte. Other remux-only
optimizations are not implemented. Input seeking is decoded by FFmpeg for accurate
trim boundaries, within one output video frame/audio encoder packet.

Hardware selection checks the compiled encoder list, then attempts a real export;
a missing device or driver falls back to x264. This is runtime validation, not a
claim that any hardware was tested in this container. VA-API selects the first
render node; multi-GPU selection is not implemented. Quality mode defaults to
software. No benchmark or minimal-RAM claim has been made.
