"""Event-driven library discovery with quiet-file detection and persistent caches."""
from pathlib import Path
import hashlib
import json
import os
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .media import probe, run

EXTENSIONS = {'.mp4', '.mkv', '.mov', '.webm'}


def state_dir(kind='config'):
    fallback = Path.home() / ('.cache' if kind == 'cache' else '.local/share' if kind == 'data' else '.config')
    root = Path(os.environ.get(f'XDG_{kind.upper() if kind != "data" else "DATA"}_HOME', fallback)) / 'clipshare'
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.replace(path)


class Library(FileSystemEventHandler):
    def __init__(self, folders, callback):
        self.folders = [Path(p) for p in folders]
        self.callback = callback
        self.pending = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.observer = Observer()
        self.cache = state_dir('cache')

    def start(self):
        self.thread = threading.Thread(target=self.bootstrap, daemon=True)
        self.thread.start()

    def bootstrap(self):
        try:
            folders = [folder for folder in self.folders if folder.is_dir()]
            for folder in folders:
                if self.stop.is_set():
                    return
                self.observer.schedule(self, str(folder), recursive=True)
            if self.stop.is_set():
                return
            self.observer.start()
            for folder in folders:
                for root, _, files in os.walk(folder):
                    if self.stop.is_set():
                        return
                    for name in files:
                        self.enqueue(Path(root) / name)
            self.work()
        except Exception as error:
            self.callback(('error', 'Folder monitoring', str(error)))
        finally:
            self.observer.stop()
            if self.observer.is_alive():
                self.observer.join()

    def close(self):
        self.stop.set()
        self.observer.stop()
        self.thread.join(timeout=.05)

    def enqueue(self, path):
        path = Path(path)
        if path.suffix.lower() in EXTENSIONS:
            with self.lock:
                self.pending[path] = (time.monotonic(), None, 0)

    def on_any_event(self, event):
        if event.event_type not in {'created', 'modified', 'deleted', 'moved'}:
            return
        if event.is_directory:
            if event.event_type in {'created', 'moved'}:
                folder = Path(getattr(event, 'dest_path', '') or event.src_path)
                for root, _, files in os.walk(folder):
                    for name in files:
                        self.enqueue(Path(root) / name)
            elif event.event_type == 'deleted':
                self.callback(('remove_tree', event.src_path, None))
            if event.event_type == 'moved':
                self.callback(('remove_tree', event.src_path, None))
            return
        self.enqueue(event.src_path)
        if getattr(event, 'dest_path', None):
            self.enqueue(event.dest_path)

    def work(self):
        while not self.stop.wait(.5):
            with self.lock:
                items = list(self.pending.items())
            for path, entry in items:
                since, signature, failures = entry
                if time.monotonic() - since < 2:
                    continue
                try:
                    stat = path.stat()
                    current = (stat.st_size, stat.st_mtime_ns)
                except OSError:
                    self.callback(('remove', str(path), None))
                    with self.lock:
                        if self.pending.get(path) == entry:
                            self.pending.pop(path, None)
                    continue
                if signature != current:
                    with self.lock:
                        if self.pending.get(path) == entry:
                            self.pending[path] = (time.monotonic(), current, failures)
                    continue
                try:
                    key = hashlib.sha256(f'{path.resolve()}:{current}'.encode()).hexdigest()
                    metadata = self.cache / f'{key}.json'
                    thumbnail = self.cache / f'{key}.jpg'
                    info = read_json(metadata, None) or probe(path)
                    if not thumbnail.exists():
                        temporary = thumbnail.with_suffix('.part.jpg')
                        try:
                            run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', str(min(2, info['duration']/3)), '-i', str(path), '-frames:v', '1', '-vf', 'scale=360:-2', str(temporary)], self.stop)
                            temporary.replace(thumbnail)
                        finally:
                            temporary.unlink(missing_ok=True)
                    if (path.stat().st_size, path.stat().st_mtime_ns) != current:
                        self.enqueue(path)
                        continue
                    write_json(metadata, info)
                    self.callback(('clip', str(path), dict(info, thumbnail=str(thumbnail), size=stat.st_size, modified=stat.st_mtime)))
                except Exception as error:
                    if failures < 4:
                        with self.lock:
                            if self.pending.get(path) == entry:
                                self.pending[path] = (time.monotonic()+5, current, failures+1)
                        continue
                    self.callback(('error', str(path), str(error)))
                with self.lock:
                    if self.pending.get(path) == entry:
                        self.pending.pop(path, None)
