"""Verify the env profile files export the heartbeat vars OpenClaw needs."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _parse_env(path: Path) -> dict:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def test_demo_env_exports_expected_keys():
    env = _parse_env(REPO / ".env.demo")
    assert env["HB_CCTV"] == "30s"
    assert env["HB_MARKETPLACE"] == "45s"
    assert env["HB_PARTS"] == "60s"
    assert env["HB_SOSMED"] == "45s"
    assert env["HB_REPORT"] == "90s"
    assert env["LACAKIN_PROFILE"] == "demo"


def test_prod_env_exports_expected_keys():
    env = _parse_env(REPO / ".env.prod")
    assert env["HB_CCTV"] == "5m"
    assert env["HB_REPORT"] == "30m"
    assert env["LACAKIN_PROFILE"] == "prod"
