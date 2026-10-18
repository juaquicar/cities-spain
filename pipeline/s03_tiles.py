"""Pack buildings into 600 m binary tiles, a per-building attribute table and the city config JSON.

Local frame: metres from the region's landmark (the Giralda in Sevilla), x east, z south (three.js, y up).
Tile layout (little-endian, every section 4-byte aligned):
  header  u32 magic, nB, nP, nR, nV; f32 originX, originZ (the tile's centre)
  B       u32 gid[nB]; i16 year[nB]; u8 flag[nB]; u8 period[nB]; u8 floors[nB]; u8 muni[nB]; u8 use[nB]; u8 mon[nB];
          i16 base[nB] (ground level, decimetres; s06_terreno)
          u32 partStart[nB+1]
  P       f32 height[nP]; u32 ringStart[nP+1]
  R       u32 vertStart[nR+1]; u8 hole[nR]
  V       i16 xz[2*nV], decimetres from the tile origin
Every part is a prism of its height (LoD 1: the Catastro gives floors per part).
"""
import json
import os
import struct
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from .municipios import BY_CODE, ORDER
from .periods import PERIODS, period_of
from .region import DATA, REGION
from .s00_fetch_catastro import chosen

ORIGIN = Transformer.from_crs(4326, REGION.crs, always_xy=True).transform(*REGION.landmark)
TILE = float(os.environ.get("SITE_TILE", 600))  # metres; a whole province takes bigger tiles, so fewer meshes to draw
SIMPLIFY = 0.2
OUT = Path(os.environ.get("SITE_OUT", "web/data" if REGION.key == "sevilla" else DATA / "web"))  # pipeline.sites builds each site into its own folder
MAGIC = 0x33565153  # 'SQV3'
DROPPED = [0]       # rings out of i16 range, reported at the end
PACK_MAX = 8e6      # bytes per pack and per part of the attribute table
USES = [  # index = use code from s02_attributes
    ("Sin uso", "#c9c6bd"), ("Residencial", "#e8b04a"), ("Agrario", "#7aa34f"), ("Industrial", "#7d6fa8"),
    ("Oficinas", "#2f6fa8"), ("Comercial", "#d2493a"), ("Servicios públicos", "#2a9d8f"),
]


def pad4(b: bytes) -> bytes:
    return b + b"\0" * (-len(b) % 4)


def to_local(coords: np.ndarray) -> np.ndarray:
    return np.c_[coords[:, 0] - ORIGIN[0], -(coords[:, 1] - ORIGIN[1])]


def rings_of(geom):
    for poly in getattr(geom, "geoms", [geom]):
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        yield shapely.get_coordinates(poly.exterior)[:-1], 0
        for hole in poly.interiors:
            yield shapely.get_coordinates(hole)[:-1], 1


def pack_tile(origin, rows):
    cols = {k: [] for k in ("gid", "year", "flag", "period", "floors", "muni", "use", "mon", "base")}
    part_start, heights, ring_start, vert_start, holes, verts = [0], [], [0], [0], [], []
    for b in rows:
        for k in cols:
            cols[k].append(b[k])
        for h, geom in b["parts"]:
            heights.append(h)
            for ring, hole in rings_of(geom):
                if len(ring) < 3:
                    continue
                v = np.round((to_local(ring) - origin) * 10)
                if np.abs(v).max() > 32767:  # a few rural "buildings" spread over kilometres: their far pieces go
                    DROPPED[0] += 1
                    continue
                verts.append(v.astype(np.int16))
                holes.append(hole)
                vert_start.append(vert_start[-1] + len(ring))
            ring_start.append(len(holes))
        part_start.append(len(heights))
    nB, nP, nR = len(rows), len(heights), len(holes)
    V = np.concatenate(verts) if verts else np.zeros((0, 2), np.int16)
    out = struct.pack("<5I2f", MAGIC, nB, nP, nR, len(V), *origin)
    out += pad4(np.array(cols["gid"], "<u4").tobytes())
    out += pad4(np.array(cols["year"], "<i2").tobytes())
    for k in ("flag", "period", "floors", "muni", "use", "mon"):
        out += pad4(np.array(cols[k], "u1").tobytes())
    out += pad4(np.array(cols["base"], "<i2").tobytes())
    out += pad4(np.array(part_start, "<u4").tobytes())
    out += pad4(np.array(heights, "<f4").tobytes())
    out += pad4(np.array(ring_start, "<u4").tobytes())
    out += pad4(np.array(vert_start, "<u4").tobytes())
    out += pad4(np.array(holes, "u1").tobytes())
    out += pad4(V.astype("<i2").tobytes())
    return out


def turismo(b, attrs):
    """turismo.json for the viewer's "what to see" and walks (s08_turismo, pipeline/rutas.json): each place as the gid of
    its building, or, for a square or a park, its own point (x, y, z local; m, the municipality of the nearest building,
    for partial loads). Places more than FAR metres from this site's buildings are not this site's."""
    src = DATA / "turismo.parquet"
    tur = OUT / "turismo.json"
    tur.unlink(missing_ok=True)
    if not src.exists() or not len(b):
        return
    from scipy.spatial import cKDTree
    FAR = 300.0
    t = pd.read_parquet(src)
    gid = pd.Series(b.index, index=b.ref)
    xz = to_local(np.c_[t.x, t.y])
    dist, near = cKDTree(np.c_[b.x, b.z]).query(xz)
    places = {}
    for k, r in enumerate(t.itertuples()):
        e = {key: val for key, val in dict(n=r.name, wd=r.wd, sl=int(r.sl), d=r.desc, wp=r.wp, img=r.img).items() if val}
        e["score"] = float(r.score)
        if isinstance(r.ref, str) and r.ref:
            if r.ref not in gid.index:
                continue
            g = int(gid[r.ref])
            e.update(g=g, lat=float(attrs["lat"][g]), lon=float(attrs["lon"][g]))
        elif dist[k] <= FAR:
            g = int(near[k])
            e.update(x=round(float(xz[k, 0]), 1), z=round(float(xz[k, 1]), 1), y=round(float(b.base.iloc[g]), 1),
                     lat=round(float(r.lat), 6), lon=round(float(r.lon), 6), m=int(b.muni.iloc[g]))
        else:
            continue
        places[r.wd] = e
    # one label per building: the best-known item on it
    seen, top = set(), []
    for e in sorted(places.values(), key=lambda e: -e.pop("score")):
        if "g" in e and e["g"] in seen:
            continue
        seen.add(e.get("g", e["wd"]))
        top.append(e)
    n_munis = b.muni.nunique()
    top = top[:40 if n_munis == 1 else 80]
    hav = lambda a, c: 2 * 6371 * np.arcsin(np.sqrt(np.sin(np.radians(c["lat"] - a["lat"]) / 2) ** 2 + np.cos(
        np.radians(a["lat"])) * np.cos(np.radians(c["lat"])) * np.sin(np.radians(c["lon"] - a["lon"]) / 2) ** 2))
    walks = []
    routes = json.loads((Path(__file__).with_name("rutas.json")).read_text()).get(REGION.key, []) \
        if Path(__file__).with_name("rutas.json").exists() else []
    for r in routes:
        stops = [dict(places[s["wd"]], n=s.get("n") or places[s["wd"]]["n"], txt=s["txt"])
                 for s in r["stops"] if s["wd"] in places]
        if len(stops) < 3:
            continue
        stops = [{k: v for k, v in st.items() if k not in ("sl",)} for st in stops]
        km = sum(hav(a, c) for a, c in zip(stops, stops[1:]))
        walks.append(dict(id=r["id"], t=r["t"], d=r["d"], km=round(float(km), 1), stops=stops))
    tur.write_text(json.dumps(dict(destacados=top, rutas=walks), ensure_ascii=False, separators=(",", ":")))
    print(f"  turismo: {len(top)} destacados, {len(walks)} rutas")


def main():
    b = gpd.read_parquet(DATA / "buildings.parquet")
    b = b[b.muni.isin([ORDER.index(c) for c in chosen()])].sort_values(["muni", "ref"]).reset_index(drop=True)
    b["year_cat"] = b.year
    base = OUT.parent / "base.parquet" if os.environ.get("SITE_OUT") else DATA / "base.parquet"
    b["base"] = b.ref.map(pd.read_parquet(base).set_index("ref").base).fillna(0) if base.exists() else 0.0
    # Heritage buildings (s05_monumentos): the IAPH's (or Wikidata's) construction date wins over the Catastro's when
    # it is earlier. date_flag 3 dated by the IAPH or Wikidata, 4 by the start of an IAPH period only.
    mon = pd.read_parquet(DATA / "monumentos.parquet") if (DATA / "monumentos.parquet").exists() else pd.DataFrame(columns=["ref"])
    b["mon"] = b.ref.isin(mon.ref).astype(np.uint8)
    if len(mon):
        y = b.ref.map(mon.set_index("ref").y0)
        ap = b.ref.map(mon.set_index("ref").approx).fillna(False).astype(bool)
        earlier = y.notna() & (y < b.year)
        b.loc[earlier, "year"] = y[earlier].astype(int)
        b.loc[earlier, "date_flag"] = np.where(ap[earlier], 4, 3)
        b["period"] = b.year.map(period_of).astype(np.uint8)
    p = gpd.read_parquet(DATA / "parts.parquet")
    gid = {k: i for i, k in enumerate(b.ref)}

    p = p[p.ref.isin(gid)].copy()
    # LiDAR heights (s07_lidar) replace the floors estimate where there are any
    lidar = DATA / "lidar.parquet"
    p["lidar"] = False
    if lidar.exists():
        hl = p.localId.map(pd.read_parquet(lidar).set_index("localId").h_lidar)
        p["lidar"] = hl.notna()
        p["h"] = hl.fillna(p.h)
        top = p.groupby("ref").h.max()
        b["height"] = b.ref.map(top).fillna(b.height)
    b["hsrc"] = b.ref.isin(p.ref[p.lidar]).astype(np.uint8)
    p["geometry"] = shapely.simplify(p.geometry.values, SIMPLIFY, preserve_topology=True)
    parts = p.groupby("ref")[["h", "geometry"]].apply(lambda d: list(zip(d.h, d.geometry))).to_dict()
    # a building with no parts in the Catastro stands as one prism of its footprint
    for r, g, h in zip(b.ref, b.geometry, b.height):
        parts.setdefault(r, [(float(h), shapely.simplify(g, SIMPLIFY, preserve_topology=True))])

    cen = to_local(np.c_[b.geometry.centroid.x, b.geometry.centroid.y])
    b["x"], b["z"] = cen[:, 0], cen[:, 1]
    b["tx"] = np.floor(b.x / TILE).astype(int)
    b["tz"] = np.floor(b.z / TILE).astype(int)

    for old in OUT.glob("pack*.bin"):
        old.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    index, blobs = [], {}
    # One tile per municipality and square, so that a viewer can load a few municipalities and nothing else.
    for (muni, tx, tz), grp in b.groupby(["muni", "tx", "tz"]):
        origin = np.array([(tx + 0.5) * TILE, (tz + 0.5) * TILE])  # the centre: vertices are i16 decimetres from it
        rows = [dict(gid=gid[r.ref], year=int(r.year), flag=int(r.date_flag), period=int(r.period),
                     floors=int(r.floors), muni=int(r.muni), use=int(r.use), mon=int(r.mon),
                     base=int(round(r.base * 10)), parts=parts[r.ref])
                for r in grp.itertuples()]
        name = f"{muni}_{tx}_{tz}"
        blobs[name] = pack_tile(origin, rows)
        cx, cz = origin
        index.append(dict(file=name, muni=int(muni), n=len(rows), dist=round(float(np.hypot(cx, cz)))))
    index.sort(key=lambda t: t["dist"])

    # Packs by municipality, nearest the landmark first within each, so that a selection fetches only its own; each
    # one a few MB, well under the host's per-file limit (Cloudflare: 25 MiB, and no range requests).
    packs, blob = [], bytearray()

    def flush():
        if blob:
            (OUT / packs[-1]).write_bytes(blob)

    last = None
    for t in sorted(index, key=lambda t: (t["muni"], t["dist"])):
        if t["muni"] != last or (blob and len(blob) + len(blobs[t["file"]]) > PACK_MAX / 2):
            flush()
            packs.append(f"pack{len(packs)}.bin")
            blob, last = bytearray(), t["muni"]
        t.update(pack=packs[-1], offset=len(blob), length=len(blobs[t["file"]]))
        blob += blobs[t["file"]]
    flush()

    # Per-building table for the card, the filter and the histogram, in gid order.
    refs = b.ref.str.encode("ascii")
    attrs = np.zeros(len(b), dtype=[("ref", f"S{max(14, refs.str.len().max())}"), ("muni", "u1"), ("use", "u1"), ("flag", "u1"), ("floors", "u1"),
                                    ("below", "u1"), ("period", "u1"), ("year", "<i2"), ("dwell", "<u2"),
                                    ("h", "<u2"), ("area", "<u4"), ("x", "<f4"), ("z", "<f4"),
                                    ("lat", "<f4"), ("lon", "<f4"), ("ycat", "<i2"), ("mon", "u1"), ("hsrc", "u1"), ("base", "<f4")])
    attrs["ref"] = refs
    for k in ("muni", "use", "floors", "below", "period", "year", "x", "z"):
        attrs[k] = b[k]
    attrs["flag"] = b.date_flag
    attrs["ycat"] = b.year_cat; attrs["mon"] = b.mon; attrs["base"] = b.base; attrs["hsrc"] = b.hsrc
    if len(mon):
        g = b.reset_index().set_index("ref")["index"]
        cards = {}
        for r in mon.itertuples():
            if r.ref not in g:
                continue
            cards[int(g[r.ref])] = {k: v for k, v in dict(
                n=r.name, y0=None if pd.isna(r.y0) else int(r.y0), y1=None if pd.isna(r.y1) else int(r.y1),
                st=r.style, pe=r.period, ty=r.types, pr=r.prot, img=r.img, wp=r.wp,
                iaph=int(r.iaph) if getattr(r, "iaph", 0) else None, wd=getattr(r, "wd", "")).items() if v not in ("", None)}
        (OUT / "monumentos.json").write_text(json.dumps(cards, ensure_ascii=False, separators=(",", ":")))
    attrs["dwell"] = b.dwellings.clip(0, 65535)
    attrs["h"] = np.round(b.height * 10).clip(0, 65535)
    attrs["area"] = b.area
    attrs["lon"], attrs["lat"] = Transformer.from_crs(REGION.crs, 4326, always_xy=True).transform(
        b.geometry.centroid.x.to_numpy(), b.geometry.centroid.y.to_numpy())
    turismo(b, attrs)
    for old in OUT.glob("attrs*.bin"):
        old.unlink()
    # The table in parts of whole municipalities (rows are sorted by municipality), ~2 MB each: a selection fetches
    # the parts it needs. A municipality larger than PACK_MAX is cut in rows.
    attr_parts, start = [], 0
    edges = np.flatnonzero(np.diff(b.muni.to_numpy())) + 1
    bounds = list(zip([0, *edges], [*edges, len(b)]))
    rows_max = max(1, int(PACK_MAX // attrs.dtype.itemsize))

    def part(s, e):
        name = f"attrs{len(attr_parts)}.bin"
        (OUT / name).write_bytes(attrs[s:e].tobytes())
        attr_parts.append(dict(file=name, start=int(s), end=int(e), munis=sorted({int(m) for m in b.muni.iloc[s:e].unique()})))

    for s, e in bounds:
        if e - s > rows_max:
            if start < s:
                part(start, s)
            for k in range(s, e, rows_max):
                part(k, min(e, k + rows_max))
            start = e
        elif (e - start) * attrs.dtype.itemsize > 2e6 and start < s:
            part(start, s)
            start = s
    if start < len(b):
        part(start, len(b))

    munis = []
    for code in chosen():
        m = b[b.muni == ORDER.index(code)]
        if m.empty:
            continue
        x0, z0, x1, z1 = m.x.min(), m.z.min(), m.x.max(), m.z.max()
        mid = ORDER.index(code)
        # what a viewer downloads for this municipality alone: its tiles and its share of the table
        size = sum(t["length"] for t in index if t["muni"] == mid) + len(m) * attrs.dtype.itemsize
        munis.append(dict(id=mid, code=code, name=BY_CODE[code][0], n=len(m),
                          cx=round(float(m.x.median()), 1), cz=round(float(m.z.median()), 1),
                          span=round(float(max(x1 - x0, z1 - z0)), 1),
                          box=[round(float(v)) for v in (x0, z0, x1, z1)], bytes=int(size)))
    # whole area: the middle of the buildings' extent, wide enough to hold it (the capital alone when it is alone)
    x0, x1, z0, z1 = b.x.quantile(0.01), b.x.quantile(0.99), b.z.quantile(0.01), b.z.quantile(0.99)
    home = dict(cx=round(float((x0 + x1) / 2), 1), cz=round(float((z0 + z1) / 2), 1), span=float(max(x1 - x0, z1 - z0)))
    config = dict(
        city=REGION.key, label=os.environ.get("SITE_LABEL") or (munis[0]["name"] if len(munis) == 1 else REGION.label), tileSize=TILE, origin=ORIGIN,
        heritage=REGION.heritage, cadastre=REGION.cadastre, refLen=attrs.dtype["ref"].itemsize,
        home=dict(x=home["cx"], z=home["cz"], azimuth=200, elevation=40, span=min(home["span"] * 1.1, 160000)),
        periods=[dict(key=k, label=l, from_=a, to=bb, color=col) for k, l, a, bb, col in PERIODS],
        uses=[dict(label=l, color=c) for l, c in USES],
        municipios=munis,
        yearMin=int(b.year.min()), yearMax=int(b.year.max()),
        attrStride=attrs.dtype.itemsize, attrParts=attr_parts,
        attrFields={k: int(v[1]) for k, v in attrs.dtype.fields.items()},
        tiles=index, packs=packs,
        stats=dict(buildings=len(b), rounded=int((b.date_flag == 1).sum()), estimated=int((b.date_flag == 2).sum()),
                   monuments=int(b.mon.sum()), redated=int((b.date_flag >= 3).sum()),
                   lidar=int(b.hsrc.sum())),
    )
    (OUT / "city.json").write_text(json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace('"from_"', '"from"'))
    total = sum((OUT / p).stat().st_size for p in packs)
    print(f"{len(index)} teselas en {len(packs)} packs, {total/1e6:.1f} MB; attrs {attrs.nbytes/1e6:.1f} MB"
          + (f"; {DROPPED[0]} anillos fuera de rango descartados" if DROPPED[0] else ""))


if __name__ == "__main__":
    main()
