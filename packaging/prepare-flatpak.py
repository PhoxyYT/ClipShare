#!/usr/bin/env python3
"""Fetch pinned build inputs before flatpak-builder's network-isolated build."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

root = Path(__file__).resolve().parent
vendor = root/'vendor'
vendor.mkdir(exist_ok=True)
wheels = vendor/'wheels'
wheels.mkdir(exist_ok=True)
subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--platform', 'manylinux_2_28_x86_64', '--platform', 'manylinux2014_x86_64', '--python-version', '312', '--implementation', 'cp', '--abi', 'cp312', '--abi', 'abi3', '--dest', str(wheels), 'PySide6-Essentials==6.8.3', 'PySide6-Addons==6.8.3', 'watchdog==6.0.0', 'requests==2.32.5', 'setuptools==80.9.0', 'wheel==0.45.1'], check=True)
archives = [
 ('python', 'https://github.com/python/cpython/archive/refs/tags/v3.12.10.tar.gz'),
 ('x264', 'https://github.com/mirror/x264/archive/refs/heads/stable.tar.gz'),
 ('ffmpeg', 'https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n7.1.1.tar.gz')]
manifest = json.loads((root/'io.github.clipshare.ClipShare.json').read_text())
for name, url in archives:
    path = vendor/f'{name}.tar.gz'
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    for module in manifest['modules']:
        if module['name'] == name:
            module['sources'] = [{'type': 'archive', 'path': f'vendor/{name}.tar.gz', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]
(root/'io.github.clipshare.ClipShare.json').write_text(json.dumps(manifest, indent=2)+'\n')
print('Inputs downloaded and archive hashes recorded. Ready for flatpak-builder (x86_64).')
