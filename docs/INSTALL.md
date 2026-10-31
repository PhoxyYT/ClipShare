# Install ClipShare on CachyOS or Bazzite

ClipShare's intended download is **ClipShare.flatpak** on the project's
[GitHub Releases page](https://github.com/PhoxyYT/ClipShare/releases). Only use a
release that actually contains that asset. Source-code ZIP files are not installers.
The release pipeline attaches the bundle only after building it, installing it,
and passing its offline smoke test. There is no claim that a release asset exists
yet or that the pipeline has already passed.

## Install with the desktop

1. Download `ClipShare.flatpak` for an **x86_64** computer (AMD/Intel 64-bit).
2. Open it with KDE Discover or your Flatpak-capable software installer.
3. Accept the installation and required Freedesktop runtime download. The first
   install requires Internet access. You do not need Python, pip or FFmpeg installed
   on the host, and Bazzite does not need package layering or writable system files.
4. Launch **ClipShare** from the application menu. Add a folder containing clips.

The bundle includes the application, CPython, PySide6/Qt6 with QtMultimedia,
FFmpeg/FFprobe, x264, Kerberos/GSSAPI runtime libraries, watchdog, requests and their Python dependencies. Flatpak
installs the shared Freedesktop runtime separately; the bundle is not a completely
offline operating-system image. Standard Flathub remote setup may be needed on a
fresh machine. Desktop installation and the following commands need real CachyOS
and Bazzite acceptance testing before being advertised as verified.

## Terminal fallback

Bazzite normally includes Flatpak. On CachyOS, if it is missing, install Flatpak
using the system package manager (`sudo pacman -S flatpak`), then log out/in if the
app menu does not update. Run all following commands as your ordinary user:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user ./ClipShare.flatpak
flatpak run io.github.clipshare.ClipShare
```

For an update, download the newer release bundle and run:

```sh
flatpak install --user --or-update ./ClipShare.flatpak
```

GitHub bundles do not establish an automatic application update feed. `flatpak
update` updates runtimes, but a new ClipShare bundle must be downloaded until an
update repository/Flathub listing is published. The application is not currently
claimed to be listed on Flathub.

## Folders and permissions

The default permission allows reading/writing your standard Videos folder; default
exports remain in `~/Videos/ClipShare`. Other folders are selected through Qt's
portal-backed file dialog where supported. Persistent recursive folder watching
through KDE's document portal still needs testing. If a chosen folder disappears
after restart or cannot be watched, grant just that directory using Flatseal or:

```sh
flatpak override --user --filesystem="$HOME/Videoklip/Clips:ro" io.github.clipshare.ClipShare
```

For an export folder outside Videos, grant write access to just that folder:

```sh
flatpak override --user --filesystem="$HOME/ClipShare-exports" io.github.clipshare.ClipShare
```

Then choose it in ClipShare Settings. Avoid FAT/exFAT output folders for now: atomic
publication currently needs hard-link support. ext4 and Btrfs support it.

The sandbox also permits Wayland, fallback X11, PulseAudio/PipeWire's PulseAudio
socket, DRI graphics access and network for optional uploads. Network permission
is available throughout the application, but local processing needs no connection.
There is no unrestricted home/system access, system bus access, `--device=all`, or
host FFmpeg execution. DRI is needed for Qt rendering and may expose compatible GPU
devices; it does not prove GPU encoding works. This baseline FFmpeg build guarantees
no hardware-encoder support; choose **Software**. Actual GPU encoding remains a
separate unverified follow-up.

## Troubleshooting

- **No installer opens:** use the terminal installation commands above.
- **Missing runtime:** add the Flathub remote as shown, then retry installation.
- **App absent from menu:** log out/in; try `flatpak run io.github.clipshare.ClipShare`.
- **Black or crashing window:** capture terminal output. For a diagnostic software
  graphics run: `flatpak run --env=QT_QUICK_BACKEND=software --env=QT_OPENGL=software
  io.github.clipshare.ClipShare`. Hardware driver behavior has not been tested here.
- **No audio:** check the desktop mixer and app volume. PipeWire should provide its
  PulseAudio compatibility service. The offline smoke test checks decoded video
  and encoded audio, not sound from actual speakers.
- **Discord cannot receive a drag:** use Open output folder and Discord's file
  picker. Flatpak Discord may need portal access to that export. Cross-sandbox
  Wayland dragging is not verified.
- **Upload fails:** local export still works. Catbox is experimental; network access
  and current service policies must be checked separately.

Run the bundled offline diagnostic (it uses synthetic clips and temporary settings):

```sh
flatpak run --env=QT_QPA_PLATFORM=offscreen --env=QT_AUDIO_BACKEND=pulseaudio \
  --command=python3 io.github.clipshare.ClipShare -m clipshare.selftest
```

Logs/settings are under `~/.var/app/io.github.clipshare.ClipShare/`. Open the
application's diagnostic log folder from Settings. Include terminal errors and the
self-test result when filing a GitHub issue; redact personal paths if necessary.

## Uninstall

Remove ClipShare from Discover, or run:

```sh
flatpak uninstall --user io.github.clipshare.ClipShare
```

To also delete its settings, cache and upload history:

```sh
flatpak uninstall --user --delete-data io.github.clipshare.ClipShare
```

Exported clips in Videos/custom folders and original recordings remain on disk.
