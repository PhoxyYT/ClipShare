import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from clipshare.hosting import CatboxProvider, validate_url
from clipshare.media import MediaError, Cancelled


@pytest.mark.parametrize('url', ['http://files.catbox.moe/a.mp4', 'https://files.catbox.moe.evil/a', 'https://user@files.catbox.moe/a', 'https://evil.test/a', '<html>error</html>', 'https://files.catbox.moe/a\nb'])
def test_reject_urls(url):
    with pytest.raises((MediaError, ValueError)):
        validate_url(url)


def test_real_http_mock(tmp_path):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'https://files.catbox.moe/test.mp4\n')
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    path = tmp_path/'private-gaming-name.mp4'
    path.write_bytes(b'fake fixture video' * 100)
    provider = CatboxProvider()
    provider.endpoint = f'http://127.0.0.1:{server.server_port}/upload'
    try:
        assert provider.upload(path, threading.Event(), lambda n: None) == 'https://files.catbox.moe/test.mp4'
        assert b'private-gaming-name' not in seen[0]
        assert path.read_bytes() in seen[0]
        assert b'fileupload' in seen[0]
        cancel = threading.Event()
        cancel.set()
        with pytest.raises(Cancelled):
            provider.upload(path, cancel, lambda n: None)
    finally:
        server.shutdown()
        server.server_close()
