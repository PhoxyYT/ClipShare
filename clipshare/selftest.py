"""Offline installed-package checks; run with python3 -m clipshare.selftest."""
from __future__ import annotations
import hashlib
import ctypes
import json
import os
from pathlib import Path
import tempfile


def main():
    # Keep tests away from the user's library/settings, including in a Flatpak.
    with tempfile.TemporaryDirectory(prefix='clipshare-selftest-') as temporary:
        root = Path(temporary)
        for name in ('CONFIG', 'CACHE', 'DATA'):
            os.environ[f'XDG_{name}_HOME'] = str(root / name.lower())
        from PySide6.QtCore import QLibraryInfo
        # Load desktop plugins even in an offscreen test: otherwise missing X11 or
        # Wayland libraries can remain hidden until installation on a real desktop.
        qt_plugins = Path(QLibraryInfo.path(QLibraryInfo.PluginsPath))
        plugin_handles = [ctypes.CDLL(str(qt_plugins / name)) for name in (
            'platforms/libqxcb.so', 'platforms/libqwayland-egl.so',
            'platforms/libqwayland-generic.so', 'platformthemes/libqxdgdesktopportal.so')]
        from PySide6.QtCore import QEventLoop, QTimer, QUrl
        from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
        from PySide6.QtWidgets import QApplication
        from .app import Window
        from .media import Export, Track, export_clip, probe, run
        import requests
        import watchdog.observers

        source = root / 'fixture.mp4'
        run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
             'testsrc2=size=320x180:rate=30:duration=2', '-f', 'lavfi', '-i',
             'sine=frequency=440:duration=2', '-f', 'lavfi', '-i',
             'sine=frequency=880:sample_rate=48000:duration=2',
             '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'libx264',
             '-threads', '2', '-preset', 'ultrafast', '-c:a', 'aac', str(source)])
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        output = export_clip(Export(source, root, .25, 1.75, [Track(1), Track(2)], .15, 'Fast'))
        info = probe(output)
        assert info['video']['codec_name'] == 'h264'
        assert len(info['audio']) == 1 and info['audio'][0]['codec_name'] == 'aac'
        assert abs(info['duration'] - 1.5) < .1
        assert output.stat().st_size <= 150000
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        app = QApplication.instance() or QApplication([])
        window = Window()
        window.show()
        app.processEvents()
        assert window.isVisible() and window.windowTitle() == 'ClipShare'
        sink = QVideoSink()
        player = QMediaPlayer()
        player.setVideoSink(sink)
        loop = QEventLoop()
        frames, errors = [], []
        def frame_ready(frame):
            if frame.isValid():
                frames.append(frame.size().toTuple())
                loop.quit()
        def failed(*_):
            errors.append(player.errorString())
            loop.quit()
        sink.videoFrameChanged.connect(frame_ready)
        player.errorOccurred.connect(failed)
        player.setSource(QUrl.fromLocalFile(str(output)))
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(15000)
        player.play()
        loop.exec()
        timer.stop()
        player.stop()
        player.setSource(QUrl())
        window.close()
        app.processEvents()
        assert frames and not errors, f'QtMultimedia decode failed: {errors or "no valid frame in 15 seconds"}'
        print(json.dumps({'result': 'passed', 'ffmpeg': run(['ffmpeg', '-version']).splitlines()[0],
                          'export_bytes': output.stat().st_size, 'decoded_frame': frames[0],
                          'checks': ['desktop plugin dependencies', 'dependency imports', 'H264/AAC encoding', 'trim', 'mix',
                                     'size limit', 'original unchanged', 'window launch', 'QtMultimedia decode']}))


if __name__ == '__main__':
    main()
