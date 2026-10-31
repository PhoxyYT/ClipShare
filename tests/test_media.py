from pathlib import Path
import hashlib
import struct
import math
import subprocess
import threading
import pytest
from clipshare.media import Export, Track, export_clip, probe, budget, Cancelled, MediaError, run


@pytest.fixture(scope='module')
def source(tmp_path_factory):
    path = tmp_path_factory.mktemp('media')/'game play ø;$(echo nope).mkv'
    run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=60:duration=4',
         '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=4',
         '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=4',
         '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', '4',
         '-map', '0:v', '-map', '1:a', '-map', '2:a', '-map', '3:a',
         '-c:v', 'libx264', '-threads', '2', '-preset', 'ultrafast', '-c:a', 'pcm_s16le',
         '-metadata:s:a:0', 'title=Gameplay', str(path)])
    return path


def test_budget():
    assert budget(10, 60, 1) == 1112000
    with pytest.raises(MediaError):
        budget(.1, 600, 3)
    with pytest.raises(MediaError):
        budget(float('nan'), 60, 1)


def test_trim_mix_size_and_original(source, tmp_path):
    before = hashlib.sha256(source.read_bytes()).digest()
    result = export_clip(Export(source, tmp_path, .5, 3.5, [Track(1), Track(2), Track(3)], .35, 'Fast'))
    info = probe(result)
    assert result.stat().st_size <= 350000
    assert info['video']['codec_name'] == 'h264'
    assert len(info['audio']) == 1
    assert info['audio'][0]['codec_name'] == 'aac'
    assert abs(info['duration']-3) < .1
    assert abs(float(info['audio'][0]['start_time'])-float(info['video']['start_time'])) < .05
    assert hashlib.sha256(source.read_bytes()).digest() == before
    pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(result), '-map', '0:a', '-t', '1', '-ar', '8000', '-ac', '1', '-f', 'f32le', '-'])
    samples = struct.unpack('<'+'f'*(len(pcm)//4), pcm)
    def amplitude(freq):
        return abs(sum(value*complex(math.cos(2*math.pi*freq*i/8000), math.sin(2*math.pi*freq*i/8000)) for i, value in enumerate(samples)))/len(samples)
    assert amplitude(440) > .004
    assert amplitude(880) > .004
    assert amplitude(660) < .001
    assert max(map(abs, samples)) <= 1


def test_unmixed_and_hardware_fallback(source, tmp_path, monkeypatch):
    import clipshare.media as media
    monkeypatch.setattr(media, 'available_encoders', lambda: ['h264_nvenc', 'libx264'])
    original = media.run
    attempts = []
    def fail_hardware(args, *a, **kw):
        if 'h264_nvenc' in args:
            attempts.append(True)
            raise MediaError('Simulated device failure')
        return original(args, *a, **kw)
    monkeypatch.setattr(media, 'run', fail_hardware)
    result = export_clip(Export(source, tmp_path, 0, 2, [Track(1), Track(2)], 1, 'Fast', 'NVIDIA', False))
    assert attempts
    assert len(probe(result)['audio']) == 2


def test_cancel_cleanup(source, tmp_path):
    cancel = threading.Event()
    def progress(_):
        cancel.set()
    with pytest.raises(Cancelled):
        export_clip(Export(source, tmp_path, 0, 4, [Track(1)], 1, 'Quality'), cancel, progress)
    assert list(tmp_path.iterdir()) == []


def test_invalid_and_no_audio(source, tmp_path):
    with pytest.raises(MediaError):
        export_clip(Export(source, tmp_path, 3, 2, []))
    result = export_clip(Export(source, tmp_path, 0, 1, [], .2, 'Fast'))
    assert not probe(result)['audio']
    bad = tmp_path/'broken.mp4'
    bad.write_text('not a video')
    with pytest.raises(MediaError):
        probe(bad)


def test_compatible_copy_is_identical(source, tmp_path):
    first = export_clip(Export(source, tmp_path, 0, 2, [Track(1)], 1, 'Fast'))
    info = probe(first)
    second = export_clip(Export(first, tmp_path, 0, info['duration'], [Track(info['audio'][0]['index'])], 1))
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize('size', ['1920x1080', '2560x1440'])
def test_high_resolution_60fps(size, tmp_path):
    source = tmp_path/'large.mkv'
    run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=size={size}:rate=60:duration=0.5', '-c:v', 'libx264', '-threads', '2', '-preset', 'ultrafast', str(source)])
    result = export_clip(Export(source, tmp_path, 0, .5, [], .1, 'Fast'))
    assert result.stat().st_size <= 100000
    assert probe(result)['video']['height'] <= 720


def test_vfr_and_long_clip(tmp_path):
    source = tmp_path/'variable-rate.mkv'
    run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=30:duration=65',
         '-vf', r"select=if(lt(t\,30)\,not(mod(n\,3))\,1)", '-fps_mode', 'vfr',
         '-c:v', 'libx264', '-threads', '2', '-preset', 'ultrafast', str(source)])
    result = export_clip(Export(source, tmp_path, 29.25, 31.75, [], .2, 'Fast'))
    assert abs(probe(result)['duration'] - 2.5) < .15
    assert result.stat().st_size <= 200000
