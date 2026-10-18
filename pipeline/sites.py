"""One published site per selection of municipalities, each on its own Cloudflare Worker (static assets).

    uv run python -m pipeline.sites                 # build every site into dist/<site>/
    uv run python -m pipeline.sites --deploy        # … and publish them
    uv run python -m pipeline.sites tomares --deploy
    uv run python -m pipeline.sites madrid barcelona --deploy

The common steps (pipeline.build, with REGION for Madrid and Barcelona) must have run first for all the municipalities
a site needs; this only redoes the per-site outputs (ground, terrain, tiles) with REGION / SITE_MUNIS / SITE_OUT, then
copies the viewer next to them.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .municipios import ALJARAFE
from .region import REGIONS

ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID")  # unset: wrangler takes the logged-in account
# name, municipality codes (None = all built), domain, worker, title, what the page says it shows, region
SITES = [
    ("tomares", ["41093"], "tomares.quijada.uk", "tomares", None, "Tomares", "sevilla"),
    ("sevilla", ["41900"], "sevilla.quijada.uk", "sevilla-edificios", None, "Sevilla", "sevilla"),
    ("aljarafe", ALJARAFE, "aljarafe.quijada.uk", "aljarafe", "Aljarafe", "el Aljarafe", "sevilla"),
    ("sevilla-aljarafe", ["41900", *ALJARAFE], "sevilla-aljarafe.quijada.uk", "sevilla-aljarafe", "Sevilla y Aljarafe",
     "Sevilla y el Aljarafe", "sevilla"),
    ("sevilla-provincia", None, "sevilla-provincia.quijada.uk", "sevilla-provincia", "Provincia de Sevilla",
     "la provincia de Sevilla", "sevilla"),
    ("madrid", None, "madrid.quijada.uk", "madrid-edificios", None, "Madrid", "madrid"),
    ("barcelona", None, "barcelona.quijada.uk", "barcelona-edificios", None, "Barcelona", "barcelona"),
]
# page texts that name the IAPH, rewritten where Wikidata is the heritage source
WIKIDATA_PAGE = {
    "Datos del Catastro, IAPH, IGN y OpenStreetMap.": "Datos del Catastro, Wikidata, IGN y OpenStreetMap.",
    """Patrimonio: Instituto Andaluz del Patrimonio Histórico (IAPH), Patrimonio Inmueble de Andalucía, datos abiertos
      de la Junta de Andalucía; fotos y artículos de Wikidata, Wikipedia y Wikimedia Commons (cada foto con su licencia).""":
    "Patrimonio: Wikidata (CC0); fotos y artículos de Wikipedia y Wikimedia Commons (cada foto con su licencia).",
    "Los edificios catalogados por el IAPH llevan": "Los edificios con ficha en Wikidata llevan",
}
TILE = {"sevilla-provincia": 2400}  # metres; default 600 (s03_tiles)
STEPS = ["pipeline.s04_ground", "pipeline.s06_terreno", "pipeline.s03_tiles"]


def build(name, codes, label=None, place=None, region="sevilla"):
    out = Path("build") / name / "data"
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REGION=region, SITE_OUT=str(out), SITE_MUNIS=",".join(codes or []), SITE_LABEL=label or "", SITE_TILE=str(TILE.get(name, 600)))
    for step in STEPS:
        print(f"— {name}: {step.split('.')[-1]}", flush=True)
        subprocess.run([sys.executable, "-m", step], env=env, check=True)
    dist = Path("dist") / name
    shutil.rmtree(dist, ignore_errors=True)
    shutil.copytree("web", dist, ignore=shutil.ignore_patterns("data"))
    shutil.copytree(out, dist / "data", ignore=shutil.ignore_patterns("*.parquet"))
    if place:  # the page's texts name the area this site shows
        page = dist / "index.html"
        html = page.read_text().replace("Sevilla y el Aljarafe", place).replace(
            "<title>Sevilla, edificio", f"<title>{label or place}, edificio").replace(
            '<h1 id="title">Sevilla</h1>', f'<h1 id="title">{label or place}</h1>')
        if REGIONS[region].heritage == "wikidata":
            for a, b in WIKIDATA_PAGE.items():
                assert a in html, a
                html = html.replace(a, b)
        page.write_text(html)
    return dist


def config(name, domain, worker):
    f = Path("sites") / f"{name}.jsonc"
    f.parent.mkdir(exist_ok=True)
    cfg = dict(
        name=worker, compatibility_date="2026-10-12",
        assets=dict(directory=f"../dist/{name}"),
        routes=[dict(pattern=domain, custom_domain=True)],
    )
    if ACCOUNT:
        cfg["account_id"] = ACCOUNT
    f.write_text(json.dumps(cfg, indent=2) + "\n")
    return f


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    deploy = "--deploy" in sys.argv
    for name, codes, domain, worker, label, place, region in SITES:
        if args and name not in args:
            continue
        dist = build(name, codes, label, place, region)
        size = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
        print(f"{name}: {size / 1e6:.1f} MB en {dist}", flush=True)
        if deploy:
            subprocess.run(["npx", "wrangler", "deploy", "-c", str(config(name, domain, worker))], check=True)


if __name__ == "__main__":
    main()
