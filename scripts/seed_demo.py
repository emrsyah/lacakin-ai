"""
Seed the demo case so judges can see findings within seconds, not minutes.

Creates:
  - shared/CONTEXT.md for case 'demo-001'
  - shared/photos/reference.jpg (placeholder — replace with real photo before demo)
  - a fake Tokopedia listing HTML page served from shared/fake_listings/ so the
    marketplace agent reliably finds something on its first tick
  - a row in lacakin.db so REPORT works immediately
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SHARED = Path(os.environ.get("LACAKIN_SHARED", str(Path.home() / "lacakin" / "shared")))
DB = Path(os.environ.get("LACAKIN_DB", str(Path.home() / "lacakin" / "lacakin.db")))

SHARED.mkdir(parents=True, exist_ok=True)
(SHARED / "photos").mkdir(exist_ok=True)
(SHARED / "findings").mkdir(exist_ok=True)
(SHARED / "fake_listings").mkdir(exist_ok=True)

now = datetime.now(timezone.utc).isoformat(timespec="seconds")

(SHARED / "CONTEXT.md").write_text(f"""# Case demo-001
- Status: ACTIVE
- Reported: {now}
- Motor: Honda Beat 2022, warna merah-hitam
- Plat: D 1234 ABC
- Last seen: Jl. Ir. H. Juanda (Dago), 14:00
- Ciri unik:
  - Stiker MotoGP merah di tangki
  - Lecet di spakbor depan
  - Velg racing aftermarket warna emas
- Photo: ./shared/photos/reference.jpg
- Search radius: 5km from last seen
- Updated: {now}
""")

# Copy real reference photo from demo_assets if available, else placeholder.
import shutil as _shutil
ref = SHARED / "photos" / "reference.jpg"
real_ref = Path(__file__).resolve().parent.parent / "demo_assets" / "reference" / "honda-beat-reference.jpg"
if real_ref.exists():
    _shutil.copy(real_ref, ref)
elif not ref.exists():
    ref.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")

(SHARED / "fake_listings" / "tokopedia-honda-beat-merah.html").write_text("""
<!doctype html><html><head><title>Honda Beat 2022 Merah Hitam Stiker MotoGP - Bandung</title></head>
<body>
  <h1>Honda Beat 2022 Merah Hitam Stiker MotoGP - BU MURAH</h1>
  <p>Rp 12.500.000</p>
  <p>Lokasi: Bandung, Jawa Barat</p>
  <p>Motor mulus, ada stiker MotoGP di tangki, velg racing emas.
     Surat lengkap (katanya). Plat dikaburkan di foto. BU cepat, nego tipis.</p>
  <img src="https://placehold.co/600x400?text=Honda+Beat+Merah" />
</body></html>
""")

DB.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(DB, isolation_level=None)
conn.executescript((Path(__file__).parent.parent / "mcp" / "db_mcp" / "schema.sql").read_text())
conn.execute("""
INSERT OR REPLACE INTO cases(id, status, created_at, updated_at, context_md)
VALUES('demo-001', 'ACTIVE', ?, ?, ?)
""", (now, now, (SHARED / "CONTEXT.md").read_text()))

print(f"Seeded demo-001 in {DB}")
print(f"CONTEXT.md at {SHARED / 'CONTEXT.md'}")
print(f"Fake listing at {SHARED / 'fake_listings' / 'tokopedia-honda-beat-merah.html'}")
print("Replace shared/photos/reference.jpg with a real Honda Beat photo before recording.")
