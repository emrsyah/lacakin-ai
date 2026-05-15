"""Five-second sanity check before each demo. No gateway needed."""
import sys
from pathlib import Path
# Ensure repo root is on path when run as `python scripts/smoke_e2e.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.a2a_mcp.server import send, list_inbox, consume, ttl_decrement
from mcp.polisi_mcp.server import draft_laporan
from mcp.vision_mcp import fixture_cache, sonnet_reason


def main():
    print("[1/4] A2A inbox roundtrip...")
    cid = send(case_id="smoke", from_agent="mata", to_agent="cadang",
               reason="test", payload={})
    msgs = list_inbox(to_agent="cadang")
    assert msgs, "A2A inbox empty"
    consume([msgs[0]["id"]])
    print("  OK")

    print("[2/4] Polisi laporan render...")
    out = draft_laporan(
        pelapor_nama="Smoke", motor_jenis="Bebek",
        merk_model_tahun="Honda Beat 2022", warna="Merah",
        plat="D 1234 ABC", ciri_unik=["test"], lokasi_terakhir="Dago",
        hari_kejadian="Senin", jam_kejadian="14:00",
    )
    assert "LAPORAN KEHILANGAN" in out["markdown"]
    print("  OK")

    print("[3/4] Vision fixture cache...")
    staged = Path("demo_assets/cctv_clips/staged-motor-frame.jpg")
    if staged.exists():
        cached = fixture_cache.lookup(str(staged))
        assert cached is not None, "Demo fixture not registered — run register_demo_fixtures.py"
        out = sonnet_reason.reason_about_candidate(
            image_path=str(staged), context_md="test", source_type="cctv"
        )
        assert out["match_confidence"] >= 0.7
        print(f"  OK (confidence {out['match_confidence']})")
    else:
        print("  SKIP (staged frame not placed yet — add demo_assets/cctv_clips/staged-motor-frame.jpg)")

    print("[4/4] Schema sanity...")
    assert "match_confidence" in sonnet_reason.RESPONSE_KEYS
    print("  OK")

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
