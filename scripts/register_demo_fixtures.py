"""Pre-register the staged CCTV image + staged listing image in the vision
fixture cache so the Sonnet calls are instant + deterministic during demo."""
from pathlib import Path
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
    "narrative": "Listing curiga di Tokopedia 32 menit lalu — semua sinyal cocok.",
    "route_to": [],
}


def main():
    cctv_img = ROOT / "cctv_clips" / "staged-motor-frame.jpg"
    listing_img = ROOT / "fake_listings" / "staged-motor-frame.jpg"
    assert cctv_img.exists(), f"Place a real JPG at {cctv_img}"
    assert listing_img.exists(), f"Place a real JPG at {listing_img}"
    h1 = fixture_cache.register_fixture(str(cctv_img), CCTV_RESPONSE)
    h2 = fixture_cache.register_fixture(str(listing_img), LISTING_RESPONSE)
    print(f"Registered CCTV fixture: {h1[:12]}...")
    print(f"Registered listing fixture: {h2[:12]}...")


if __name__ == "__main__":
    main()
