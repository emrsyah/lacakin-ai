"""Polisi-MCP — renders the laporan template from case context."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import sys as _sys, importlib as _il
    _real_mcp = _il.import_module("mcp.server.fastmcp")
    FastMCP = _real_mcp.FastMCP
    del _real_mcp, _sys, _il
except (ModuleNotFoundError, ImportError):
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name): self.name = name
        def tool(self): return lambda f: f
        def run(self): pass

TEMPLATE = (Path(__file__).parent / "template_laporan.md").read_text()
mcp = FastMCP("polisi-mcp")


@mcp.tool()
def draft_laporan(
    pelapor_nama: str,
    motor_jenis: str,
    merk_model_tahun: str,
    warna: str,
    plat: str,
    ciri_unik: list[str],
    lokasi_terakhir: str,
    hari_kejadian: str,
    jam_kejadian: str,
    kronologi_singkat: str = "",
) -> dict[str, Any]:
    """Render the laporan template with the provided case fields.
    Returns {markdown: str}. Polisi-AI agent posts this verbatim in the group."""
    rendered = TEMPLATE.format(
        pelapor_nama=pelapor_nama or "(belum diisi)",
        tanggal=datetime.now().strftime("%d %B %Y"),
        motor_jenis=motor_jenis,
        merk_model_tahun=merk_model_tahun,
        warna=warna,
        plat=plat,
        ciri_unik=", ".join(ciri_unik) if ciri_unik else "(tidak ada)",
        lokasi_terakhir=lokasi_terakhir,
        hari_kejadian=hari_kejadian,
        jam_kejadian=jam_kejadian,
        kronologi_singkat=kronologi_singkat or
            "Motor diketahui hilang setelah pemilik kembali ke lokasi parkir.",
    )
    return {"markdown": rendered}


if __name__ == "__main__":
    mcp.run()
