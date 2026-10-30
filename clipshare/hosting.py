"""Streaming anonymous Catbox uploads. Provider policy verification is documented."""
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
import uuid
import requests
from .media import Cancelled, MediaError


class HostingProvider(Protocol):
    name: str
    def upload(self, path: Path, cancel, progress): ...


def validate_url(value):
    value = value.strip()
    url = urlparse(value)
    if (url.scheme != 'https' or url.hostname != 'files.catbox.moe' or
        url.username or url.password or url.port not in (None, 443) or
        not url.path.startswith('/') or len(url.path) < 3 or url.query or url.fragment or
        any(c.isspace() for c in value)):
        raise MediaError('Catbox returned an invalid sharing URL')
    return value


class CatboxProvider:
    name = 'Catbox'
    endpoint = 'https://catbox.moe/user/api.php'
    max_bytes = 200_000_000

    def upload(self, path, cancel, progress):
        size = path.stat().st_size
        if not 0 < size <= self.max_bytes:
            raise MediaError('Catbox uploads must be between 1 byte and 200 MB')
        boundary = 'clipshare' + uuid.uuid4().hex
        # Neutral filename avoids disclosing the user's original recording name.
        header = (f'--{boundary}\r\nContent-Disposition: form-data; name="reqtype"\r\n\r\nfileupload\r\n'
                  f'--{boundary}\r\nContent-Disposition: form-data; name="fileToUpload"; filename="clip{path.suffix.lower()}"\r\n'
                  'Content-Type: application/octet-stream\r\n\r\n').encode()
        footer = f'\r\n--{boundary}--\r\n'.encode()
        class Body:
            def __len__(self):
                return len(header) + size + len(footer)
            def __iter__(self):
                if cancel.is_set():
                    raise Cancelled('Upload cancelled')
                yield header
                sent = 0
                with path.open('rb') as stream:
                    while chunk := stream.read(256 * 1024):
                        if cancel.is_set():
                            raise Cancelled('Upload cancelled')
                        yield chunk
                        sent += len(chunk)
                        progress(sent / size * .99)
                yield footer
        try:
            with requests.post(self.endpoint, data=Body(), headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, timeout=(10, 30), allow_redirects=False, stream=True) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(1024):
                    if cancel.is_set():
                        raise Cancelled('Upload cancelled')
                    content.extend(chunk)
                    if len(content) > 4096:
                        raise MediaError('Catbox returned an unexpectedly large response')
                result = validate_url(content.decode('utf-8'))
            progress(1)
            return result
        except requests.RequestException as error:
            if cancel.is_set():
                raise Cancelled('Upload cancelled') from error
            raise MediaError(f'Upload failed: {error}') from error
