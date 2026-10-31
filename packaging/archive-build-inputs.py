#!/usr/bin/env python3
"""Combine Git source and verified inputs in a fresh PAX archive.

Appending to git archive's tar keeps its ustar filename limits, even when GNU tar
is passed --format=pax. Create a new PAX archive instead so long wheel names fit.
"""
from pathlib import Path
import subprocess
import tarfile
import tempfile


def main():
    root = Path(__file__).resolve().parent.parent
    inputs = root / 'packaging/vendor/release-sources'
    if not (inputs / 'SOURCES.json').is_file():
        raise RuntimeError('Run packaging/prepare-flatpak.py first')
    output = root / 'dist/ClipShare-build-inputs.tar.gz'
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='clipshare-archive-') as temporary:
        source = Path(temporary) / 'source.tar'
        subprocess.run(['git', 'archive', '--format=tar', '--prefix=ClipShare/',
                        f'--output={source}', 'HEAD'], cwd=root, check=True)
        partial = output.with_suffix(output.suffix + '.part')
        try:
            with tarfile.open(source, 'r') as code, tarfile.open(partial, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
                for member in code:
                    archive.addfile(member, code.extractfile(member) if member.isfile() else None)
                archive.add(inputs, arcname='packaging/vendor/release-sources')
            partial.replace(output)
        finally:
            partial.unlink(missing_ok=True)
    print(f'Created {output}')


if __name__ == '__main__':
    main()
