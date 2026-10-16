"""Download Catastro INSPIRE Buildings (building + buildingpart GML) for the chosen municipalities.

    uv run python -m pipeline.s00_fetch_catastro tomares sevilla
    uv run python -m pipeline.s00_fetch_catastro todos

The list of chosen municipalities is kept in data/municipios.json; every later step reads it. Running this again
with new names adds them to the list; zips already on disk are not downloaded again.
"""
import json
import os
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

import requests

from .municipios import BY_CODE, ORDER, resolve

FEED = "https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/41/{folder}/A.ES.SDGC.BU.{code}.zip"
RAW = Path("data/raw/catastro")
CHOSEN = Path("data/municipios.json")


def chosen() -> list[str]:
    """The municipalities built so far; SITE_MUNIS (codes, comma-separated) narrows them for one site (pipeline.sites)."""
    codes = json.loads(CHOSEN.read_text()) if CHOSEN.exists() else []
    site = os.environ.get("SITE_MUNIS")
    return [c for c in codes if c in site.split(",")] if site else codes


def fetch(code: str):
    name, folder = BY_CODE[code]
    zpath = RAW / f"{code}.zip"
    if not zpath.exists():
        url = FEED.format(folder=quote(f"{code}-{folder}"), code=code)
        print(f"  {name}: descargando…", flush=True)
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        zpath.write_bytes(r.content)
    out = RAW / code
    if not out.exists():
        with zipfile.ZipFile(zpath) as z:
            z.extractall(out)
    print(f"  {name}: {zpath.stat().st_size / 1e6:.1f} MB")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    codes = resolve(sys.argv[1:]) if len(sys.argv) > 1 else []
    codes = sorted(set(json.loads(CHOSEN.read_text()) if CHOSEN.exists() else []) | set(codes), key=ORDER.index)
    if not codes:
        raise SystemExit("Indica municipios: p. ej. `tomares sevilla` o `todos`")
    for c in codes:
        fetch(c)
    CHOSEN.write_text(json.dumps(codes))
    print(len(codes), "municipios:", ", ".join(BY_CODE[c][0] for c in codes))


if __name__ == "__main__":
    main()
