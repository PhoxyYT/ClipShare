import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_AUDIO_BACKEND', 'pulseaudio')
from PySide6.QtWidgets import QApplication
from clipshare.app import Window


def test_window_and_settings(tmp_path, monkeypatch):
    for kind in ('CONFIG', 'DATA', 'CACHE'):
        monkeypatch.setenv(f'XDG_{kind}_HOME', str(tmp_path/kind))
    app = QApplication.instance() or QApplication([])
    window = Window()
    window.show()
    app.processEvents()
    assert window.windowTitle() == 'ClipShare'
    assert window.mix.isChecked()
    window.save_audio()
    assert window.settings_path.exists()
    assert not window.drag.isEnabled()
    window.close()
    app.processEvents()
