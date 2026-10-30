"""Non-destructive FFmpeg processing. No shell commands or in-memory videos."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import math
import os
import subprocess
import tempfile
import threading
import time
import uuid


class MediaError(Exception):
    pass


class Cancelled(MediaError):
    pass


def run(args, cancel=None, progress=None, duration=0):
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled("Cancelled")
    # stderr is a file so FFmpeg cannot deadlock on a full pipe.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors, text=True)
        lines = []
        def read():
            for line in process.stdout:
                if progress and line.startswith("out_time_us=") and duration:
                    try:
                        progress(min(0.99, max(0, int(line.split('=')[1]) / 1e6 / duration)))
                    except ValueError:
                        pass
                else:
                    lines.append(line)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            while process.poll() is None:
                if cancel.wait(0.1):
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise Cancelled("Cancelled; incomplete output removed")
            reader.join()
            if process.returncode:
                errors.seek(0, 2)
                errors.seek(max(0, errors.tell() - 4000))
                raise MediaError(errors.read().decode(errors='replace').strip())
            return ''.join(lines)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            reader.join(timeout=3)
            process.stdout.close()


def probe(path: Path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)]))
    videos = [s for s in data['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if not videos:
        raise MediaError('This file contains no playable video')
    duration = float(data.get('format', {}).get('duration', 0))
    if not math.isfinite(duration) or duration <= 0:
        raise MediaError('The recording has no valid duration yet')
    return {**data, 'video': videos[0], 'audio': [s for s in data['streams'] if s['codec_type'] == 'audio'], 'duration': duration}


@dataclass
class Track:
    index: int
    gain: float = 1.0


@dataclass
class Export:
    source: Path
    directory: Path
    start: float
    end: float
    tracks: list[Track]
    target_mb: float | None = 10
    profile: str = 'Balanced'
    encoder: str = 'Software'
    mix: bool = True


def audio_filters(tracks, mix=True):
    parts, labels = [], []
    for i, t in enumerate(tracks):
        if not math.isfinite(t.gain) or not 0 <= t.gain <= 2:
            raise MediaError('Track gain must be between 0 and 200%')
        parts.append(f'[0:{t.index}]aresample=48000:async=1:first_pts=0,aformat=channel_layouts=stereo,volume={t.gain}[a{i}]')
        labels.append(f'[a{i}]')
    if not labels:
        return '', []
    if mix:
        # Normalization avoids summing full-scale streams; limiter catches gain boosts.
        parts.append(''.join(labels) + f'amix=inputs={len(labels)}:duration=longest:dropout_transition=0:normalize=1,alimiter=limit=0.95:latency=1[mix]')
        return ';'.join(parts), ['[mix]']
    for i in range(len(labels)):
        parts.append(f'[a{i}]alimiter=limit=0.95:latency=1[out{i}]')
    return ';'.join(parts), [f'[out{i}]' for i in range(len(labels))]


def budget(target_mb, duration, audio_count):
    if not math.isfinite(target_mb) or target_mb <= 0 or not math.isfinite(duration) or duration <= 0:
        raise MediaError('Size and duration must be positive')
    audio = 128_000 * audio_count
    video = int(target_mb * 1_000_000 * 8 * .93 / duration - audio)
    if video < 60_000:
        raise MediaError('This size is too small for the selected duration and audio. Trim the clip or increase the limit.')
    return video


def available_encoders():
    text = run(['ffmpeg', '-hide_banner', '-encoders'])
    return [e for e in ('libx264', 'h264_nvenc', 'h264_vaapi', 'h264_qsv') if e in text]


def export_clip(job: Export, cancel=None, progress=None):
    cancel = cancel or threading.Event()
    source_stat = job.source.stat()
    info = probe(job.source)
    duration = job.end - job.start
    if not (math.isfinite(job.start) and math.isfinite(job.end) and 0 <= job.start < job.end <= info['duration'] + .05):
        raise MediaError('Choose a valid trim range within the clip')
    allowed = {s['index'] for s in info['audio']}
    if len({t.index for t in job.tracks}) != len(job.tracks) or any(t.index not in allowed for t in job.tracks):
        raise MediaError('Invalid or duplicate audio track selection')
    job.directory.mkdir(parents=True, exist_ok=True)
    destination = job.directory / f'{job.source.stem}-clipshare-{uuid.uuid4().hex[:10]}.mp4'
    graph, audio_maps = audio_filters(job.tracks, job.mix)
    bitrate = budget(job.target_mb, duration, len(audio_maps)) if job.target_mb else None
    preset = {'Fast': 'veryfast', 'Balanced': 'medium', 'Quality': 'slow'}.get(job.profile, 'medium')
    encoders = ['libx264']
    if job.encoder != 'Software':
        available = available_encoders()
        requested = {'NVIDIA': ['h264_nvenc'], 'VA-API': ['h264_vaapi'], 'Intel QSV': ['h264_qsv']}.get(job.encoder, ['h264_nvenc', 'h264_vaapi', 'h264_qsv'])
        encoders = [e for e in requested if e in available] + ['libx264']
    with tempfile.TemporaryDirectory(prefix='.clipshare-', dir=job.directory) as work:
        temporary = Path(work) / 'output.mp4'
        untouched = (job.start == 0 and abs(job.end-info['duration']) < .001 and
                     len(info['audio']) <= 1 and
                     [t.index for t in job.tracks] == [a['index'] for a in info['audio']] and
                     all(t.gain == 1 for t in job.tracks))
        compatible = (job.source.suffix.lower() == '.mp4' and info['video']['codec_name'] == 'h264' and
                      info['video'].get('pix_fmt') == 'yuv420p' and
                      all(a['codec_name'] == 'aac' for a in info['audio']))
        if untouched and compatible and (job.target_mb is None or source_stat.st_size <= job.target_mb*1_000_000):
            with job.source.open('rb') as source, temporary.open('xb') as target:
                while chunk := source.read(1024*1024):
                    if cancel.is_set():
                        raise Cancelled('Cancelled')
                    target.write(chunk)
                    if progress:
                        progress(min(.99, target.tell()/source_stat.st_size))
            if cancel.is_set():
                raise Cancelled('Cancelled')
            if (job.source.stat().st_size, job.source.stat().st_mtime_ns) != (source_stat.st_size, source_stat.st_mtime_ns):
                raise MediaError('The source recording changed during export; try again after recording stops')
            os.link(temporary, destination)
            if progress:
                progress(1)
            return destination
        for encoder in encoders:
            try:
                for attempt in range(3):
                    if cancel.is_set():
                        raise Cancelled('Cancelled')
                    rate = info['video'].get('avg_frame_rate', '0/1').split('/')
                    source_fps = float(rate[0])/float(rate[1]) if len(rate) == 2 and float(rate[1]) else 60
                    fps = min(source_fps or 60, 30 if bitrate and bitrate < 2_000_000 else 60)
                    height = 360 if bitrate and bitrate < 400_000 else 480 if bitrate and bitrate < 800_000 else 720 if bitrate and bitrate < 2_000_000 else 1080
                    height = min(height, int(info['video']['height']))
                    vf = f'scale=-2:{height - height % 2},fps={fps},format=yuv420p' if bitrate else 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p'
                    base = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y']
                    if encoder == 'h264_vaapi':
                        devices = sorted(Path('/dev/dri').glob('renderD*'))
                        if not devices:
                            raise MediaError('No VA-API render device')
                        base += ['-vaapi_device', str(devices[0])]
                        vf = vf.replace('format=yuv420p', 'format=nv12,hwupload')
                    base += ['-ss', str(job.start), '-i', str(job.source), '-t', str(duration)]
                    maps = ['-map', f"0:{info['video']['index']}"]
                    if graph:
                        maps += ['-filter_complex', graph]
                        for label in audio_maps:
                            maps += ['-map', label]
                    else:
                        maps += ['-an']
                    video = ['-vf', vf, '-c:v', encoder]
                    if encoder == 'libx264':
                        video += ['-preset', preset, '-threads', '2']
                    if bitrate:
                        video += ['-b:v', str(bitrate)]
                    else:
                        video += ['-crf', '18'] if encoder == 'libx264' else ['-b:v', '12000000']
                    if bitrate and encoder == 'libx264':
                        run(base + ['-map', f"0:{info['video']['index']}", '-an'] + video + ['-pass', '1', '-passlogfile', str(Path(work)/'pass'), '-progress', 'pipe:1', '-f', 'null', '/dev/null'], cancel, (lambda p: progress(p*.45)) if progress else None, duration)
                        video += ['-pass', '2', '-passlogfile', str(Path(work)/'pass')]
                    run(base + maps + video + ['-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-progress', 'pipe:1', str(temporary)], cancel, (lambda p: progress(.45+p*.54)) if progress else None, duration)
                    result = probe(temporary)
                    if len(result['audio']) != len(audio_maps):
                        raise MediaError('Output audio validation failed')
                    size = temporary.stat().st_size
                    if job.target_mb is None or size <= int(job.target_mb * 1_000_000):
                        if cancel.is_set():
                            raise Cancelled('Cancelled')
                        if (job.source.stat().st_size, job.source.stat().st_mtime_ns) != (source_stat.st_size, source_stat.st_mtime_ns):
                            raise MediaError('The source recording changed during export; try again after recording stops')
                        # Atomic publication without overwriting any existing path.
                        os.link(temporary, destination)
                        if progress:
                            progress(1)
                        return destination
                    bitrate = int(bitrate * (job.target_mb * 1_000_000 / size) * .88)
                    if bitrate < 60_000:
                        raise MediaError('Unable to meet size target; shorten the selection')
                raise MediaError('Output exceeded the size limit after three attempts')
            except Cancelled:
                raise
            except MediaError:
                if encoder == 'libx264':
                    raise
    raise MediaError('No working encoder')
