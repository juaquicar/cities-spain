"""One published site per selection of municipalities, each on its own Cloudflare Worker (static assets).

    uv run python -m pipeline.sites                 # build every site into dist/<site>/
    uv run python -m pipeline.sites --deploy        # … and publish them
    uv run python -m pipeline.sites tomares --deploy
    uv run python -m pipeline.sites madrid barcelona --deploy
    uv run python -m pipeline.sites portal --deploy     # spain-cities.quijada.uk, from the sites in dist/
    uv run python -m pipeline.sites --pages             # only web/ changed: new pages over the data already built

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


def build(name, codes, label=None, place=None, region="sevilla", pages_only=False):
    """pages_only: the viewer's files again over the data already built (after a change to web/ only)."""
    out = Path("build") / name / "data"
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REGION=region, SITE_OUT=str(out), SITE_MUNIS=",".join(codes or []), SITE_LABEL=label or "", SITE_TILE=str(TILE.get(name, 600)))
    for step in [] if pages_only else STEPS:
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


# The portal (spain-cities.quijada.uk): one page listing every area, each area a built site in its own folder, and
# nothing loads until the visitor has chosen. key, built site, name, line under it, ready-made selections.
PORTAL_DOMAIN, PORTAL_WORKER = "spain-cities.quijada.uk", "spain-cities"
PORTAL = [
    ("sevilla", "sevilla-provincia", "Sevilla", "Provincia · Andalucía",
     [("Sevilla capital", ["41900"]), ("Aljarafe", ALJARAFE), ("Sevilla y Aljarafe", ["41900", *ALJARAFE]),
      ("Toda la provincia", None)]),
    ("madrid", "madrid", "Madrid", "Ciudad · Comunidad de Madrid", []),
    ("barcelona", "barcelona", "Barcelona", "Ciudad · Cataluña", []),
]


def outline(rings, scale, x0, z0):
    """SVG path of a municipality's polygons, scaled into the picker's box, y down (the local frame is z south)."""
    d = []
    for poly in rings:
        r = poly[0]
        pts = [f"{(r[k] - x0) * scale:.1f},{(r[k + 1] - z0) * scale:.1f}" for k in range(0, len(r), 2)]
        d.append("M" + "L".join(pts) + "Z")
    return "".join(d)


def portal(deploy=False):
    from shapely.geometry import Polygon
    out = Path("dist") / PORTAL_WORKER
    shutil.rmtree(out, ignore_errors=True)
    shutil.copytree("portal", out)
    cities = []
    for key, site, name, sub, presets in PORTAL:
        src = Path("dist") / site
        if not (src / "data" / "city.json").exists():
            print(f"portal: falta dist/{site}; se omite", flush=True)
            continue
        shutil.copytree(src, out / key)
        page = out / key / "index.html"  # a link back to the list
        page.write_text(page.read_text().replace('<body>', '<body data-portal="../">', 1))
        c = json.loads((src / "data" / "city.json").read_text())
        files = {f.name: f.stat().st_size for f in (src / "data").iterdir()}
        base = sum(files.get(f, 0) for f in ("city.json", "ground.json", "terrain.bin", "monumentos.json")) + 2_600_000
        parts = [p if isinstance(p, dict) else dict(file=p) for p in c.get("attrParts", ["attrs.bin"])]
        # the outlines for the picker map: municipal boundaries simplified to a few hundred points each
        ground = json.loads((src / "data" / "ground.json").read_text())
        rings = {m["id"]: m["rings"] for m in ground["munis"]}
        xs = [v for rs in rings.values() for poly in rs for v in poly[0][0::2]]
        zs = [v for rs in rings.values() for poly in rs for v in poly[0][1::2]]
        x0, x1, z0, z1 = (min(xs), max(xs), min(zs), max(zs)) if xs else (0, 1, 0, 1)
        scale = 400 / max(x1 - x0, z1 - z0)
        tol = max(x1 - x0, z1 - z0) / 900
        munis = []
        for m in c["municipios"]:
            simple = []
            for poly in rings.get(m["id"], []):
                r = poly[0]
                g = Polygon(list(zip(r[0::2], r[1::2]))).simplify(tol)
                if not g.is_empty and g.geom_type == "Polygon":
                    simple.append([[v for xy in g.exterior.coords for v in xy]])
            munis.append(dict(
                code=m["code"], name=m["name"], n=m["n"], id=m["id"],
                packs=sorted({t["pack"] for t in c["tiles"] if t.get("muni", m["id"]) == m["id"]}),
                parts=[p["file"] for p in parts if not p.get("munis") or m["id"] in p["munis"]],
                d=outline(simple, scale, x0, z0)))
        cities.append(dict(key=key, name=name, sub=sub, buildings=c["stats"]["buildings"],
                           monuments=c["stats"].get("monuments", 0), heritage=c.get("heritage", "iaph"),
                           years=[c["yearMin"], c["yearMax"]], base=base, files=files,
                           view=[round((x1 - x0) * scale), round((z1 - z0) * scale)],
                           presets=[dict(name=n, codes=codes or []) for n, codes in presets],
                           municipios=munis))
    (out / "cities.json").write_text(json.dumps(cities, ensure_ascii=False, separators=(",", ":")))
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"portal: {len(cities)} áreas, {size / 1e6:.1f} MB en {out}", flush=True)
    if deploy:
        subprocess.run(["npx", "wrangler", "deploy", "-c", str(config(PORTAL_WORKER, PORTAL_DOMAIN, PORTAL_WORKER))],
                       check=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    deploy, pages_only = "--deploy" in sys.argv, "--pages" in sys.argv
    if args == ["portal"]:  # only the portal, from the sites already in dist/
        return portal(deploy)
    for name, codes, domain, worker, label, place, region in SITES:
        if args and name not in args:
            continue
        dist = build(name, codes, label, place, region, pages_only)
        size = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
        print(f"{name}: {size / 1e6:.1f} MB en {dist}", flush=True)
        if deploy:
            subprocess.run(["npx", "wrangler", "deploy", "-c", str(config(name, domain, worker))], check=True)


if __name__ == "__main__":
    main()
