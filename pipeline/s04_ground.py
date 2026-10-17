"""Municipal boundaries and water from OpenStreetMap (ODbL), as flat polygons in the local frame.

web/data/ground.json: {"munis": [{"id", "rings": [[x, z, x, z, …], …]}], "water": [[ring, hole, …], …]}
Every polygon is a list of rings, the first the outline and the rest its holes; coordinates in metres, rounded.
"""
import json
import math
import time
import zlib
from pathlib import Path

import numpy as np
import requests
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from .municipios import ORDER
from .s00_fetch_catastro import chosen
from .s03_tiles import OUT, to_local

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
# the Catastro numbers Sevilla and the four newest municipalities its own way; INE and OSM use these
INE = {"41900": "41091", "41103": "41901", "41104": "41902", "41105": "41903", "41106": "41904"}
CACHE = Path("data/raw/osm")
PROVINCE = "36.8,-6.6,38.25,-4.6"  # Sevilla province, south-west-north-east; cheaper for Overpass than an area
TO_UTM = Transformer.from_crs(4326, 25830, always_xy=True).transform


def overpass(query: str, name: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{name}.json"
    if not f.exists():
        for attempt in range(6):
            url = OVERPASS[attempt % len(OVERPASS)]
            try:
                r = requests.post(url, data={"data": query}, headers={"User-Agent": "sevilla-edificios/0.1"}, timeout=300)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                print(f"  overpass {url}: {e}; reintento", flush=True)
                time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit("Overpass no responde")
        f.write_text(r.text)
    return json.loads(f.read_text())["elements"]


def line(geom):
    x, y = TO_UTM([p["lon"] for p in geom], [p["lat"] for p in geom])
    return LineString(np.c_[x, y]) if len(geom) > 1 else None


def assemble(el):
    """A relation (or a closed way) as a shapely polygon: outer ways minus inner ways."""
    if el["type"] == "way":
        g = line(el["geometry"])
        return Polygon(g.coords) if g and g.is_closed and len(g.coords) > 3 else None
    rings = {"outer": [], "inner": []}
    for m in el.get("members", []):
        if m["type"] == "way" and m.get("geometry") and m.get("role") in ("outer", "inner", ""):
            g = line(m["geometry"])
            if g:
                rings["inner" if m["role"] == "inner" else "outer"].append(g)
    outer = unary_union(list(polygonize(unary_union(rings["outer"])))) if rings["outer"] else None
    if outer is None or outer.is_empty:
        return None
    if rings["inner"]:
        outer = outer.difference(unary_union(list(polygonize(unary_union(rings["inner"])))))
    return outer


def polys(geom, tol):
    geom = shapely.make_valid(shapely.simplify(geom, tol, preserve_topology=True))
    out = []
    for p in getattr(geom, "geoms", [geom]):
        if p.geom_type != "Polygon" or p.area < 50:
            continue
        out.append([np.round(to_local(np.asarray(r.coords)[:-1]), 1).ravel().tolist()
                    for r in (p.exterior, *p.interiors)])
    return out


def main():
    codes = chosen()
    ine = "|".join(INE.get(c, c) for c in codes)
    # a dozen municipalities per request: the whole province with geometry is more than Overpass will answer
    rels = []
    for k in range(0, len(codes), 12):
        part = "|".join(INE.get(c, c) for c in codes[k:k + 12])
        rels += overpass(f'[out:json][timeout:240];rel["boundary"="administrative"]["admin_level"="8"]'
                         f'["ine:municipio"~"^({part})$"]({PROVINCE});out geom;',
                         "munis_" + "_".join(codes[k:k + 12]) if len(codes) < 6
                         else f"munis_{len(codes[k:k + 12])}_{zlib.crc32(part.encode()):08x}")
    back = {INE.get(c, c): c for c in codes}
    munis, shapes = [], []
    for el in rels:
        code = back.get(el["tags"].get("ine:municipio"))
        g = assemble(el)
        if code is None or g is None:
            continue
        shapes.append(g)
        munis.append(dict(id=ORDER.index(code), rings=polys(g, 4)))
    area = unary_union(shapes)
    minx, miny, maxx, maxy = area.buffer(1500).bounds
    to_ll = Transformer.from_crs(25830, 4326, always_xy=True).transform
    w, s = to_ll(minx, miny)
    e, n = to_ll(maxx, maxy)
    # water in cells of at most ~0.4°, for the same reason; a cell Overpass will not answer is split in four
    def water_in(s, w, n, e, depth=0):
        bbox = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"
        try:
            return overpass(f'[out:json][timeout:240];(way["natural"="water"]({bbox});rel["natural"="water"]({bbox});'
                            f'way["waterway"="riverbank"]({bbox});rel["waterway"="riverbank"]({bbox}););out geom;',
                            f"water_{bbox.replace(',', '_')}")
        except SystemExit:
            if depth >= 2:
                raise
            print(f"  agua {bbox}: en cuatro partes", flush=True)
            ms, mw = (s + n) / 2, (w + e) / 2
            return [el for q in ((s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e))
                    for el in water_in(*q, depth + 1)]

    nx, ny = max(1, math.ceil((e - w) / 0.4)), max(1, math.ceil((n - s) / 0.4))
    els = [el for i in range(nx) for j in range(ny)
           for el in water_in(s + (n - s) * j / ny, w + (e - w) * i / nx, s + (n - s) * (j + 1) / ny, w + (e - w) * (i + 1) / nx)]
    # a body of water across two cells comes twice
    els = list({(el["type"], el["id"]): el for el in els}.values())
    water = [g for g in map(assemble, els) if g is not None and not g.is_empty]
    water = unary_union([shapely.make_valid(g) for g in water]).intersection(area.buffer(1500)) if water else Polygon()
    ground = dict(munis=munis, water=polys(water, 2))
    (OUT / "ground.json").write_text(json.dumps(ground, separators=(",", ":")))
    print(f"{len(munis)} términos municipales, {len(ground['water'])} polígonos de agua, "
          f"{(OUT / 'ground.json').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
