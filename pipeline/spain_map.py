"""The portal's map of Spain: autonomous communities, neighbours in faint, the Canaries in a box off Almería.

    uv run python -m pipeline.spain_map        # writes portal/spain.json (done once; it is in the repo)

Natural Earth 1:10m admin-1 (provinces dissolved by community) and 1:50m countries, public domain, downloaded into
data/raw/ne/. `project(lon, lat)` places a point on the same drawing; sites.py uses it for each city's dot.
"""
import json
import math
from pathlib import Path

import geopandas as gpd
from shapely.affinity import affine_transform
from shapely.geometry import box

NE = Path("data/raw/ne")
OUT = Path("portal/spain.json")
S = 92.0                                  # drawing units per degree of latitude
K = math.cos(math.radians(40))            # one longitude scale for the whole country
W, H = 1000, 900
# the Canaries are moved: their box sits in the Alboran Sea's corner of the drawing
CAN = dict(lon=-18.3, lat=29.5, x=605, y=712)
CAN_BOX = (-18.3, 27.55, -13.3, 29.5)


def canaries(lon, lat):
    return CAN_BOX[0] <= lon <= CAN_BOX[2] and CAN_BOX[1] <= lat <= CAN_BOX[3]


def project(lon, lat):
    if canaries(lon, lat):
        return round((lon - CAN["lon"]) * K * S + CAN["x"], 1), round((CAN["lat"] - lat) * S + CAN["y"], 1)
    return round((lon + 9.6) * K * S, 1), round((44.0 - lat) * S, 1)


def geo_to_draw(g, can):
    if can:
        return affine_transform(g, [K * S, 0, 0, -S, CAN["x"] - CAN["lon"] * K * S, CAN["y"] + CAN["lat"] * S])
    return affine_transform(g, [K * S, 0, 0, -S, 9.6 * K * S, 44.0 * S])


def path(g):
    polys = [g] if g.geom_type == "Polygon" else list(g.geoms) if hasattr(g, "geoms") else []
    out = []
    for p in polys:
        if p.geom_type != "Polygon" or p.area < 1:
            continue
        for ring in [p.exterior, *p.interiors]:
            c = list(ring.coords)
            out.append("M" + "L".join(f"{x:.0f},{y:.0f}" for x, y in c[:-1]) + "Z")
    return "".join(out)


def main():
    a1 = gpd.read_file(NE / "ne_10m_admin_1_states_provinces.geojson")
    es = a1[(a1.adm0_a3 == "ESP") & ~a1.region.isin(["Ceuta", "Melilla"])]
    ccaa = es.dissolve("region").geometry.simplify(0.012)
    land = []
    for name, g in ccaa.items():
        can = name == "Canary Is."
        land.append(dict(name=name, d=path(geo_to_draw(g, can))))
    countries = gpd.read_file(NE / "ne_50m_admin_0_countries.geojson")
    near = countries[countries.ADM0_A3.isin(["PRT", "FRA", "AND"])].geometry
    near = near.intersection(box(-10.5, 35.0, 5.5, 44.6)).simplify(0.02)
    context = "".join(path(geo_to_draw(g, False)) for g in near if not g.is_empty)
    x0, y0 = project(CAN_BOX[0], CAN_BOX[3])
    x1, y1 = project(CAN_BOX[2], CAN_BOX[1])
    OUT.write_text(json.dumps(dict(w=W, h=H, ccaa=land, context=context,
                                   canarias=[x0 - 8, y0 - 8, x1 - x0 + 16, y1 - y0 + 16]), ensure_ascii=False,
                              separators=(",", ":")))
    print(f"{OUT}: {OUT.stat().st_size / 1e3:.0f} kB, {len(land)} comunidades")


if __name__ == "__main__":
    main()
