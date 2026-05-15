"""Pre-register the staged CCTV image + staged listing image in the vision
fixture cache so the Sonnet calls are instant + deterministic during demo."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mcp.vision_mcp import fixture_cache

ROOT = Path(__file__).resolve().parent.parent / "demo_assets"

CCTV_RESPONSE = {
    "match_confidence": 0.86,
    "matches": [
        "Warna body merah-hitam — sesuai dengan referensi",
        "Plat samar terbaca 'D 12?? AB?' — cocok parsial",
        "Stiker merah di tangki — konsisten dengan stiker MotoGP",
    ],
    "mismatches": [],
    "suspicious_signals": [
        "Pengendara tidak pakai helm",
        "Motor jalan pelan, sering toleh ke belakang",
    ],
    "narrative": "Honda Beat merah-hitam terlihat melaju ke selatan di Simpang Dago.",
    "route_to": [
        {"agent": "parts", "reason": "motor menuju selatan, cari velg emas di Buah Batu / Kiaracondong"}
    ],
}

LISTING_RESPONSE = {
    "match_confidence": 0.91,
    "matches": [
        "Honda Beat merah-hitam dengan stiker MotoGP di tangki — sangat mirip referensi",
    ],
    "mismatches": [],
    "suspicious_signals": [
        "Plat sengaja dikaburkan di semua foto",
        "Harga Rp 12.500.000 — di bawah pasar Rp 15-16jt",
        "Akun baru, rating 0",
    ],
    "narrative": "Listing curiga di Facebook Marketplace 32 menit lalu — semua sinyal cocok.",
    "route_to": [
        {"agent": "report", "reason": "kandidat marketplace HIGH — rangkum bareng temuan CCTV"}
    ],
}


def _ensure_distinct(path: Path) -> None:
    """Append a trailing null byte so this image no longer collides with a
    byte-identical sibling. JPEG decoders ignore data after the EOI marker,
    so the rendered pixels are unchanged but the SHA differs."""
    data = path.read_bytes()
    if data.endswith(b"\x00"):
        return
    path.write_bytes(data + b"\x00")


def main():
    cctv_img = ROOT / "cctv_clips" / "staged-motor-frame.jpg"
    listing_img = ROOT / "fake_listings" / "staged-motor-frame.jpg"
    assert cctv_img.exists(), f"Place a real JPG at {cctv_img}"
    assert listing_img.exists(), f"Place a real JPG at {listing_img}"

    if fixture_cache.hash_image(str(cctv_img)) == fixture_cache.hash_image(str(listing_img)):
        _ensure_distinct(listing_img)

    h1 = fixture_cache.register_fixture(str(cctv_img), CCTV_RESPONSE)
    h2 = fixture_cache.register_fixture(str(listing_img), LISTING_RESPONSE)
    fixture_cache.register_score(str(cctv_img), text_image=0.31)
    fixture_cache.register_score(str(listing_img), image_image=0.82)
    print(f"Registered CCTV fixture: {h1[:12]}...")
    print(f"Registered listing fixture: {h2[:12]}...")


if __name__ == "__main__":
    main()
