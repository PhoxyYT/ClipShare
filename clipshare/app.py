from __future__ import annotations
from datetime import datetime
from pathlib import Path
import logging
import sys
import threading
from PySide6.QtCore import Qt, Signal, QObject, QThreadPool, QRunnable, QUrl, QSize, QMimeData, QTimer
from PySide6.QtGui import QIcon, QPixmap, QDrag, QDesktopServices, QPalette, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QListWidget, QListWidgetItem, QSplitter, QFileDialog,
    QDoubleSpinBox, QCheckBox, QSlider, QProgressBar, QMessageBox, QScrollArea, QGroupBox, QDialog)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from .media import Export, Track, export_clip, available_encoders, run
from .library import Library, state_dir, read_json, write_json
from .hosting import CatboxProvider

STYLE = '''
QWidget { background: #15191f; color: #e6edf3; font-size: 13px; }
QMainWindow { background: #101419; }
QLabel#title { font-size: 26px; font-weight: 700; }
QLabel#muted { color: #98a7b7; }
QPushButton { background: #26313e; border: 1px solid #354455; border-radius: 7px; padding: 9px 14px; }
QPushButton:hover { background: #35475a; }
QPushButton:disabled { color: #697785; background: #1c232c; }
QPushButton#primary { background: #4c72ed; border-color: #6789ff; color: white; font-weight: 600; }
QLineEdit, QComboBox, QDoubleSpinBox { background: #202731; border: 1px solid #354455; border-radius: 6px; padding: 7px; }
QListWidget { background: #101419; border: none; padding: 8px; }
QListWidget::item { background: #1b232d; border-radius: 9px; padding: 10px; margin: 4px; }
QListWidget::item:selected { background: #2d426b; }
QGroupBox { border: 1px solid #303d4b; border-radius: 9px; margin-top: 18px; padding-top: 15px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; color: #aebed1; }
QProgressBar { border: none; background: #26313e; border-radius: 4px; height: 8px; }
QProgressBar::chunk { background: #7194ff; border-radius: 4px; }
QSlider::groove:horizontal { background: #354455; height: 5px; border-radius: 2px; }
QSlider::handle:horizontal { background: #88a6ff; width: 14px; margin: -5px 0; border-radius: 7px; }
QScrollArea { border: none; }
'''


def button(text, action, primary=False):
    b = QPushButton(text)
    b.clicked.connect(action)
    if primary:
        b.setObjectName('primary')
    return b


def label(text, muted=False):
    w = QLabel(text)
    w.setWordWrap(True)
    if muted:
        w.setObjectName('muted')
    return w


def row(*widgets):
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout


class Signals(QObject):
    done = Signal(object)
    error = Signal(str)
    progress = Signal(float)
    library = Signal(object)


class Task(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = Signals()
        self.cancel = threading.Event()
    def run(self):
        try:
            self.signals.done.emit(self.fn(self.cancel, self.signals.progress.emit))
        except Exception as error:
            logging.exception('Background task failed')
            self.signals.error.emit(str(error))


class FileDrag(QPushButton):
    def __init__(self):
        super().__init__('Drag exported clip to Discord')
        self.path = None
        self.setEnabled(False)
    def mousePressEvent(self, event):
        self.origin = event.position().toPoint()
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event):
        if self.path and event.buttons() & Qt.LeftButton and (event.position().toPoint()-self.origin).manhattanLength() >= QApplication.startDragDistance():
            drag = QDrag(self)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(self.path))])
            drag.setMimeData(mime)
            drag.exec(Qt.CopyAction)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ClipShare')
        self.resize(1260, 850)
        self.settings_path = state_dir() / 'settings.json'
        self.settings = read_json(self.settings_path, {})
        self.clips = {}
        self.selected = None
        self.output = None
        self.task = None
        self.library = None
        self.previewing = False
        self.preview_path = None
        self.tracks = []
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.events = Signals()
        self.events.library.connect(self.library_event)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        title = label('ClipShare')
        title.setObjectName('title')
        settings_button = button('Settings', self.preferences)
        settings_button.setFixedWidth(110)
        layout.addLayout(row(title, label('Your best moments. Ready to share.', True), settings_button))
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        gallery = QWidget()
        left = QVBoxLayout(gallery)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search your clips…')
        self.search.textChanged.connect(self.render_gallery)
        self.sort = QComboBox()
        self.sort.addItems(['Newest first', 'Name', 'Largest first'])
        self.sort.currentIndexChanged.connect(self.render_gallery)
        left.addLayout(row(self.search, self.sort))
        left.addWidget(button('＋ Add clip folder', self.add_folder))
        self.count = label('Add a recording folder to get started.', True)
        left.addWidget(self.count)
        self.gallery = QListWidget()
        self.gallery.setViewMode(QListWidget.IconMode)
        self.gallery.setResizeMode(QListWidget.Adjust)
        self.gallery.setMovement(QListWidget.Static)
        self.gallery.setIconSize(QSize(240, 135))
        self.gallery.setGridSize(QSize(278, 235))
        self.gallery.itemClicked.connect(self.select_clip)
        left.addWidget(self.gallery)
        splitter.addWidget(gallery)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        detail = QWidget()
        scroll.setWidget(detail)
        self.detail = QVBoxLayout(detail)
        self.name = label('Select a clip')
        self.name.setObjectName('title')
        self.detail.addWidget(self.name)
        self.video = QVideoWidget()
        self.video.setMinimumSize(360, 210)
        self.detail.addWidget(self.video)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(lambda *_: self.status.setText('Playback: '+self.player.errorString()))
        self.play = button('Play / Pause', self.toggle_play)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.player.durationChanged.connect(lambda n: self.seek.setRange(0, n))
        self.player.positionChanged.connect(self.position_changed)
        self.detail.addLayout(row(self.play, self.seek))
        self.detail.addWidget(label('Source playback uses one audio track. Use Preview mix to hear your selected tracks together.', True))
        trim = QGroupBox('Trim · seconds')
        tl = QVBoxLayout(trim)
        self.start = QDoubleSpinBox()
        self.end = QDoubleSpinBox()
        for spin in (self.start, self.end):
            spin.setDecimals(3)
            spin.setMaximum(864000)
            spin.valueChanged.connect(self.trim_changed)
        tl.addLayout(row(label('In'), self.start, label('Out'), self.end))
        self.start_handle = QSlider(Qt.Horizontal)
        self.end_handle = QSlider(Qt.Horizontal)
        self.start_handle.sliderMoved.connect(lambda n: self.start.setValue(n/1000))
        self.end_handle.sliderMoved.connect(lambda n: self.end.setValue(n/1000))
        tl.addWidget(self.start_handle)
        tl.addWidget(self.end_handle)
        self.duration = label('', True)
        tl.addWidget(self.duration)
        self.detail.addWidget(trim)
        self.audio_box = QGroupBox('Audio tracks')
        self.audio_layout = QVBoxLayout(self.audio_box)
        self.detail.addWidget(self.audio_box)
        self.mix = QCheckBox('Combine Audio Tracks')
        self.mix.setChecked(self.settings.get('mix', True))
        self.detail.addWidget(self.mix)
        self.detail.addWidget(label('Check track names before mixing: exclude a full-mix track if its sources are also selected.', True))
        self.detail.addLayout(row(button('Preview mix', self.preview_mix), button('Save audio defaults', self.save_audio)))
        self.target = QComboBox()
        self.target.addItems(['10', '25', '50', '100', 'Custom'])
        self.custom = QDoubleSpinBox()
        self.custom.setRange(.1, 10000)
        self.custom.setValue(self.settings.get('target', 10))
        self.custom.setSuffix(' MB')
        self.target.setCurrentText(str(int(self.custom.value())) if self.custom.value() in (10,25,50,100) else 'Custom')
        self.target.currentTextChanged.connect(lambda text: self.custom.setValue(float(text)) if text != 'Custom' else None)
        self.profile = QComboBox()
        self.profile.addItems(['Fast', 'Balanced', 'Quality'])
        self.profile.setCurrentText(self.settings.get('profile', 'Balanced'))
        self.detail.addLayout(row(label('Size limit'), self.target, self.custom))
        self.detail.addLayout(row(label('Profile'), self.profile))
        advanced = QGroupBox('Advanced encoding')
        advanced.setCheckable(True)
        advanced.setChecked(False)
        al = QVBoxLayout(advanced)
        self.encoder = QComboBox()
        self.encoder.addItems(['Software', 'Auto hardware', 'NVIDIA', 'VA-API', 'Intel QSV'])
        self.encoder.setCurrentText(self.settings.get('encoder', 'Software'))
        self.encoder.setVisible(False)
        advanced.toggled.connect(self.encoder.setVisible)
        al.addWidget(self.encoder)
        self.detail.addWidget(advanced)
        self.compress = button('Compress for Discord', self.compress_clip, True)
        self.detail.insertWidget(1, self.compress)
        self.compress.setText(f'Compress for Discord · {self.custom.value():g} MB')
        self.custom.valueChanged.connect(lambda n: self.compress.setText(f'Compress for Discord · {n:g} MB'))
        self.detail.addWidget(button('Export quality clip · no size limit', self.quality_export))
        self.detail.addLayout(row(button('Upload original', lambda: self.upload(True)), button('Upload exported clip', lambda: self.upload(False))))
        self.drag = FileDrag()
        self.detail.addWidget(self.drag)
        self.detail.addLayout(row(button('Open output folder', self.open_output), button('Copy file', self.copy_file), button('Copy path', self.copy_path)))
        self.link = QLineEdit()
        self.link.setReadOnly(True)
        self.link.setPlaceholderText('Sharing link appears after a successful upload')
        self.detail.addWidget(self.link)
        self.detail.addLayout(row(button('Copy link', lambda: QApplication.clipboard().setText(self.link.text())), button('Open link', self.open_link)))
        self.detail.addStretch()
        splitter.addWidget(scroll)
        splitter.setSizes([650, 550])
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status = label('Ready · all local processing works offline', True)
        self.cancel_button = button('Cancel', self.cancel_task)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setFixedWidth(110)
        layout.addLayout(row(self.status, self.cancel_button))
        layout.addWidget(self.progress)
        self.restart_library()

    def persist(self):
        write_json(self.settings_path, self.settings)

    def restart_library(self):
        if self.library:
            self.library.close()
        self.clips.clear()
        self.render_gallery()
        generation = object()
        self.library_generation = generation
        def callback(event):
            if self.library_generation is generation:
                self.events.library.emit(event)
        self.library = Library(self.settings.get('folders', []), callback)
        self.library.start()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choose a recording folder')
        if folder:
            self.settings['folders'] = list(dict.fromkeys(self.settings.get('folders', [])+[folder]))
            self.persist()
            self.restart_library()

    def library_event(self, event):
        kind, path, value = event
        if kind == 'clip':
            self.clips[path] = value
        elif kind == 'remove':
            self.clips.pop(path, None)
        elif kind == 'remove_tree':
            self.clips = {p: v for p, v in self.clips.items() if not Path(p).is_relative_to(path)}
        else:
            logging.warning('Discovery: %s: %s', path, value)
            self.status.setText(f'Could not read {Path(path).name}; see diagnostic log')
        self.render_gallery()

    def render_gallery(self):
        self.gallery.clear()
        items = [(p, v) for p, v in self.clips.items() if self.search.text().lower() in Path(p).name.lower()]
        key = (lambda item: -item[1]['modified']) if self.sort.currentIndex() == 0 else (lambda item: Path(item[0]).name.lower()) if self.sort.currentIndex() == 1 else (lambda item: -item[1]['size'])
        for path, info in sorted(items, key=key):
            video = info['video']
            text = f"{Path(path).name}\n{info['duration']:.1f}s · {video['width']}×{video['height']} · {info['size']/1e6:.1f} MB\n{datetime.fromtimestamp(info['modified']):%d %b %Y · %H:%M}"
            item = QListWidgetItem(QIcon(info['thumbnail']), text)
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.gallery.addItem(item)
        self.count.setText(f'{len(items)} clips · {len(self.settings.get("folders", []))} watched folders')

    def select_clip(self, item):
        self.selected = Path(item.data(Qt.UserRole))
        info = self.clips[str(self.selected)]
        self.name.setText(self.selected.name)
        self.previewing = False
        self.player.setSource(QUrl.fromLocalFile(str(self.selected)))
        self.start.setValue(0)
        self.end.setValue(info['duration'])
        self.start_handle.setRange(0, int(info['duration']*1000))
        self.end_handle.setRange(0, int(info['duration']*1000))
        self.trim_changed()
        while self.audio_layout.count():
            self.audio_layout.takeAt(0).widget().deleteLater()
        self.tracks = []
        defaults = self.settings.get('audio', [])
        for n, stream in enumerate(info['audio']):
            box = QWidget()
            layout = QHBoxLayout(box)
            name = stream.get('tags', {}).get('title', f'Track {n+1}')
            check = QCheckBox(f"{name} · {stream['codec_name']} · {stream.get('channels', '?')}ch · {stream.get('sample_rate', '?')} Hz")
            default = defaults[n] if n < len(defaults) else {'enabled': True, 'gain': 1}
            check.setChecked(default['enabled'])
            gain = QDoubleSpinBox()
            gain.setRange(0, 2)
            gain.setSingleStep(.1)
            gain.setValue(default['gain'])
            gain.setSuffix(' ×')
            layout.addWidget(check)
            layout.addWidget(gain)
            self.audio_layout.addWidget(box)
            self.tracks.append((stream['index'], check, gain))
        if not self.tracks:
            self.audio_layout.addWidget(label('No audio streams'))

    def trim_changed(self):
        self.start_handle.setValue(int(self.start.value()*1000))
        self.end_handle.setValue(int(self.end.value()*1000))
        self.duration.setText(f'Selection: {max(0, self.end.value()-self.start.value()):.3f} seconds')

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if not self.previewing and not self.start.value()*1000 <= self.player.position() < self.end.value()*1000:
                self.player.setPosition(int(self.start.value()*1000))
            self.player.play()

    def position_changed(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        if not self.previewing and self.end.value() > 0 and position >= self.end.value()*1000:
            self.player.pause()

    def job(self, target):
        if not self.selected:
            raise ValueError('Select a clip first')
        return Export(self.selected, Path(self.settings.get('output', str(Path.home()/'Videos'/'ClipShare'))), self.start.value(), self.end.value(), [Track(i, g.value()) for i, c, g in self.tracks if c.isChecked()], target, self.profile.currentText(), self.encoder.currentText(), self.mix.isChecked())

    def begin(self, fn, done, message):
        if self.task:
            self.status.setText('A task is already running. Finish or cancel it first.')
            return
        self.task = Task(fn)
        self.task.signals.progress.connect(lambda n: self.progress.setValue(int(n*100)))
        self.task.signals.done.connect(lambda result: self.finished(done, result))
        self.task.signals.error.connect(self.failed)
        self.progress.setValue(0)
        self.cancel_button.setEnabled(True)
        self.status.setText(message)
        self.pool.start(self.task)

    def finished(self, done, result):
        self.task = None
        self.cancel_button.setEnabled(False)
        self.progress.setValue(100)
        done(result)

    def failed(self, error):
        self.task = None
        self.cancel_button.setEnabled(False)
        self.status.setText(error[-700:])

    def cancel_task(self):
        if self.task:
            self.task.cancel.set()
            self.status.setText('Cancelling…')

    def compress_clip(self):
        self.do_export(self.custom.value())

    def quality_export(self):
        self.do_export(None)

    def do_export(self, target):
        try:
            job = self.job(target)
            self.settings.update(target=self.custom.value(), profile=self.profile.currentText(), encoder=self.encoder.currentText())
            self.persist()
            self.begin(lambda c, p: export_clip(job, c, p), self.exported, 'Encoding · selected audio is preserved')
        except ValueError as error:
            self.status.setText(str(error))

    def exported(self, path):
        self.output = path
        self.drag.path = path
        self.drag.setEnabled(True)
        self.status.setText(f'Export ready · {path.stat().st_size/1e6:.2f} MB · {path.name}')

    def preview_mix(self):
        try:
            job = self.job(None)
            job.directory = state_dir('cache') / 'previews'
            job.profile = 'Fast'
            job.mix = True
            def ready(path):
                self.player.stop()
                self.player.setSource(QUrl())
                if self.preview_path:
                    self.preview_path.unlink(missing_ok=True)
                self.preview_path = path
                self.previewing = True
                self.player.setSource(QUrl.fromLocalFile(str(path)))
                self.player.play()
                self.status.setText('Playing the rendered mix for the selected trim range')
            self.begin(lambda c, p: export_clip(job, c, p), ready, 'Preparing exact audio mix preview…')
        except ValueError as error:
            self.status.setText(str(error))

    def save_audio(self):
        self.settings['audio'] = [{'enabled': c.isChecked(), 'gain': g.value()} for _, c, g in self.tracks]
        self.settings['mix'] = self.mix.isChecked()
        self.persist()
        self.status.setText('Audio defaults saved by track order')

    def upload(self, original):
        path = self.selected if original else self.output
        if not path or not path.exists():
            self.status.setText('Select a source clip or export a clip first')
            return
        if self.task:
            self.status.setText('Finish the current task first')
            return
        text = ('The original file and all its existing audio streams will be uploaded unchanged.' if original else 'The last exported clip will be uploaded.')
        text += '\n\nCatbox is a third-party public file host. Links are not guaranteed permanent. Current policy and live uploads have not been verified by this build. Review https://catbox.moe/faq.php and https://catbox.moe/legal.php before use.\n\nUpload this file: '+path.name+'?'
        if QMessageBox.question(self, 'Upload to Catbox', text) != QMessageBox.Yes:
            return
        def ready(url):
            self.link.setText(url)
            QApplication.clipboard().setText(url)
            history_path = state_dir('data')/'uploads.json'
            history = read_json(history_path, [])
            history.append({'name': path.name, 'url': url, 'date': datetime.now().isoformat()})
            write_json(history_path, history)
            self.status.setText('Uploaded · sharing link copied')
        self.begin(lambda c, p: CatboxProvider().upload(path, c, p), ready, 'Uploading to Catbox…')

    def open_link(self):
        if self.link.text():
            QDesktopServices.openUrl(QUrl(self.link.text()))

    def open_output(self):
        path = self.output.parent if self.output else Path(self.settings.get('output', str(Path.home()/'Videos'/'ClipShare')))
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def copy_file(self):
        if self.output:
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(self.output))])
            QApplication.clipboard().setMimeData(mime)

    def copy_path(self):
        if self.output:
            QApplication.clipboard().setText(str(self.output))

    def preferences(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('ClipShare settings')
        dialog.resize(600, 480)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('Recording folders'))
        folders = QListWidget()
        folders.addItems(self.settings.get('folders', []))
        layout.addWidget(folders)
        def remove():
            if folders.currentRow() >= 0:
                folders.takeItem(folders.currentRow())
                self.settings['folders'] = [folders.item(i).text() for i in range(folders.count())]
                self.persist()
                self.restart_library()
        layout.addWidget(button('Remove selected folder', remove))
        output = label(self.settings.get('output', str(Path.home()/'Videos'/'ClipShare')), True)
        def choose():
            path = QFileDialog.getExistingDirectory(dialog, 'Choose output folder')
            if path:
                self.settings['output'] = path
                self.persist()
                output.setText(path)
        layout.addWidget(output)
        layout.addWidget(button('Choose output folder', choose))
        layout.addWidget(label('Dark theme · English · resolution and FPS adapt automatically to the size budget', True))
        def diagnostics():
            self.begin(lambda c, p: run(['ffmpeg', '-version']).splitlines()[0]+'\nEncoders compiled in (device availability checked during export): '+', '.join(available_encoders()), lambda text: QMessageBox.information(self, 'Diagnostics', text), 'Checking FFmpeg…')
        layout.addWidget(button('FFmpeg diagnostics', diagnostics))
        layout.addWidget(button('Open diagnostic log folder', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(state_dir('data'))))))
        def history():
            entries = read_json(state_dir('data')/'uploads.json', [])
            QMessageBox.information(dialog, 'Upload history', '\n\n'.join(f"{e['date']} · {e['name']}\n{e['url']}" for e in entries[-30:]) or 'No uploads yet')
        layout.addWidget(button('Upload history', history))
        layout.addWidget(button('Close', dialog.accept))
        dialog.exec()

    def closeEvent(self, event):
        if self.task:
            self.cancel_task()
            self.status.setText('Cancelling task; close the window again when it has stopped.')
            event.ignore()
            return
        self.player.stop()
        self.player.setSource(QUrl())
        if self.preview_path:
            self.preview_path.unlink(missing_ok=True)
        if self.library:
            self.library.close()
        event.accept()


def main():
    logging.basicConfig(filename=state_dir('data')/'clipshare.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    app = QApplication(sys.argv)
    app.setApplicationName('ClipShare')
    app.setDesktopFileName('io.github.clipshare.ClipShare')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    if '--smoke-test' in sys.argv:
        QTimer.singleShot(1000, window.close)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
