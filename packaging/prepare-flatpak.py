#!/usr/bin/env python3
"""Download and verify pinned third-party inputs for corresponding-source archives.

Flatpak-builder downloads these itself; this helper is for release redistribution,
not a required pre-build step. It never rewrites the manifest or resolves versions.
"""
import hashlib
import json
import shutil
from pathlib import Path
import urllib.request


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root/'io.github.clipshare.ClipShare.json').read_text())
    output = root/'vendor'/'release-sources'
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for module in manifest['modules']:
        for source in module['sources']:
            if 'url' not in source:
                continue
            url, expected = source['url'], source['sha256']
            name = url.rsplit('/', 1)[-1]
            target = output / (module['name']+'-'+name)
            if not target.exists():
                temporary = target.with_suffix(target.suffix+'.part')
                try:
                    cached = root.parent/'.flatpak-builder'/'downloads'/expected/name
                    if cached.is_file():
                        shutil.copyfile(cached, temporary)
                    else:
                        urllib.request.urlretrieve(url, temporary)
                    if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                        raise ValueError(f'Checksum mismatch: {url}')
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise ValueError(f'Cached input checksum mismatch: {target.name}')
            records.append({'file':target.name,'url':url,'sha256':expected})
    (output/'SOURCES.json').write_text(json.dumps(records, indent=2)+'\n')
    print(f'Verified {len(records)} source archives/wheels in {output}')


if __name__ == '__main__':
    main()
