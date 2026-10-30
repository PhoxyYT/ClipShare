import time
from pathlib import Path
from clipshare.library import Library
from clipshare.media import run


def wait_for(check, seconds=12):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        if check():
            return
        time.sleep(.1)
    assert check()


def test_discovery_rename_delete_and_cache(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path/'cache'))
    recordings = tmp_path/'recordings'
    nested = recordings/'game'
    nested.mkdir(parents=True)
    events = []
    library = Library([recordings], events.append)
    library.start()
    try:
        source = nested/'clip.mp4'
        run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=size=160x90:duration=0.3', '-c:v', 'libx264', '-threads', '1', str(source)])
        wait_for(lambda: any(e[0] == 'clip' for e in events))
        first = next(e for e in events if e[0] == 'clip')
        assert Path(first[2]['thumbnail']).exists()
        assert list((tmp_path/'cache'/'clipshare').glob('*.json'))
        renamed = nested/'renamed.mp4'
        source.rename(renamed)
        wait_for(lambda: any(e[:2] == ('clip', str(renamed)) for e in events))
        wait_for(lambda: any(e[:2] == ('remove', str(source)) for e in events))
        renamed.unlink()
        wait_for(lambda: any(e[:2] == ('remove', str(renamed)) for e in events))
    finally:
        library.close()
