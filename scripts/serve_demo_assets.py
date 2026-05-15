"""Serve demo_assets/ on a local port. Use during demo + dev.

Cameras.json point cctv URLs at this server; marketplace agent's fake
Tokopedia link points here too."""
import http.server
import socketserver
from pathlib import Path

PORT = 8765
ROOT = Path(__file__).resolve().parent.parent / "demo_assets"

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

if __name__ == "__main__":
    with socketserver.TCPServer(("0.0.0.0", PORT), H) as httpd:
        print(f"Serving {ROOT} at http://0.0.0.0:{PORT}")
        httpd.serve_forever()
