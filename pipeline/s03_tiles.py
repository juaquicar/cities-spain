"""Pack buildings into 600 m binary tiles, a per-building attribute table and the city config JSON.

Local frame: metres from the Giralda, x east, z south (three.js, y up).
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
from .s00_fetch_catastro import chosen

GIRALDA = Transformer.from_crs(4326, 25830, always_xy=True).transform(-5.99260, 37.38620)
TILE = float(os.environ.get("SITE_TILE", 600))  # metres; a whole province takes bigger tiles, so fewer meshes to draw
SIMPLIFY = 0.2
OUT = Path(os.environ.get("SITE_OUT", "web/data"))  # pipeline.sites builds each site into its own folder
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
    return np.c_[coords[:, 0] - GIRALDA[0], -(coords[:, 1] - GIRALDA[1])]


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


def main():
    b = gpd.read_parquet("data/buildings.parquet")
    b = b[b.muni.isin([ORDER.index(c) for c in chosen()])].sort_values(["muni", "ref"]).reset_index(drop=True)
    b["year_cat"] = b.year
    base = OUT.parent / "base.parquet" if os.environ.get("SITE_OUT") else Path("data/base.parquet")
    b["base"] = b.ref.map(pd.read_parquet(base).set_index("ref").base).fillna(0) if base.exists() else 0.0
    # Heritage buildings (s05_monumentos): the IAPH's construction date wins over the Catastro's when it is earlier.
    # date_flag 3 dated by the IAPH or Wikidata, 4 by the start of an IAPH period only.
    mon = pd.read_parquet("data/monumentos.parquet") if Path("data/monumentos.parquet").exists() else pd.DataFrame(columns=["ref"])
    b["mon"] = b.ref.isin(mon.ref).astype(np.uint8)
    if len(mon):
        y = b.ref.map(mon.set_index("ref").y0)
        ap = b.ref.map(mon.set_index("ref").approx).fillna(False).astype(bool)
        earlier = y.notna() & (y < b.year)
        b.loc[earlier, "year"] = y[earlier].astype(int)
        b.loc[earlier, "date_flag"] = np.where(ap[earlier], 4, 3)
        b["period"] = b.year.map(period_of).astype(np.uint8)
    p = gpd.read_parquet("data/parts.parquet")
    gid = {k: i for i, k in enumerate(b.ref)}

    p = p[p.ref.isin(gid)].copy()
    # LiDAR heights (s07_lidar) replace the floors estimate where there are any
    lidar = Path("data/lidar.parquet")
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
    for (tx, tz), grp in b.groupby(["tx", "tz"]):
        origin = np.array([(tx + 0.5) * TILE, (tz + 0.5) * TILE])  # the centre: vertices are i16 decimetres from it
        rows = [dict(gid=gid[r.ref], year=int(r.year), flag=int(r.date_flag), period=int(r.period),
                     floors=int(r.floors), muni=int(r.muni), use=int(r.use), mon=int(r.mon),
                     base=int(round(r.base * 10)), parts=parts[r.ref])
                for r in grp.itertuples()]
        name = f"{tx}_{tz}"
        blobs[name] = pack_tile(origin, rows)
        cx, cz = origin
        index.append(dict(file=name, n=len(rows), dist=round(float(np.hypot(cx, cz)))))
    index.sort(key=lambda t: t["dist"])

    # A few packs, nearest the Giralda first, so the city loads centre-out in few requests; each one well under the
    # host's per-file limit (Cloudflare: 25 MiB).
    total = sum(len(v) for v in blobs.values())
    target = min(PACK_MAX, max(total / 16, 1e6))
    packs, blob = [], bytearray()

    def flush():
        if blob:
            (OUT / packs[-1]).write_bytes(blob)

    for t in index:
        if not packs or (blob and len(blob) + len(blobs[t["file"]]) > target):
            flush()
            packs.append(f"pack{len(packs)}.bin")
            blob = bytearray()
        t.update(pack=packs[-1], offset=len(blob), length=len(blobs[t["file"]]))
        blob += blobs[t["file"]]
    flush()

    # Per-building table for the card, the filter and the histogram, in gid order.
    attrs = np.zeros(len(b), dtype=[("ref", "S14"), ("muni", "u1"), ("use", "u1"), ("flag", "u1"), ("floors", "u1"),
                                    ("below", "u1"), ("period", "u1"), ("year", "<i2"), ("dwell", "<u2"),
                                    ("h", "<u2"), ("area", "<u4"), ("x", "<f4"), ("z", "<f4"),
                                    ("lat", "<f4"), ("lon", "<f4"), ("ycat", "<i2"), ("mon", "u1"), ("hsrc", "u1"), ("base", "<f4")])
    attrs["ref"] = b.ref.str.encode("ascii")
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
                st=r.style, pe=r.period, ty=r.types, pr=r.prot, img=r.img, wp=r.wp, iaph=int(r.iaph)).items() if v not in ("", None)}
        (OUT / "monumentos.json").write_text(json.dumps(cards, ensure_ascii=False, separators=(",", ":")))
    attrs["dwell"] = b.dwellings.clip(0, 65535)
    attrs["h"] = np.round(b.height * 10).clip(0, 65535)
    attrs["area"] = b.area
    attrs["lon"], attrs["lat"] = Transformer.from_crs(25830, 4326, always_xy=True).transform(
        b.geometry.centroid.x.to_numpy(), b.geometry.centroid.y.to_numpy())
    for old in OUT.glob("attrs*.bin"):
        old.unlink()
    rows = max(1, int(PACK_MAX // attrs.dtype.itemsize))
    attr_parts = []
    for k in range(0, len(attrs), rows):
        attr_parts.append("attrs.bin" if len(attrs) <= rows else f"attrs{k // rows}.bin")
        (OUT / attr_parts[-1]).write_bytes(attrs[k:k + rows].tobytes())

    munis = []
    for code in chosen():
        m = b[b.muni == ORDER.index(code)]
        if m.empty:
            continue
        x0, z0, x1, z1 = m.x.min(), m.z.min(), m.x.max(), m.z.max()
        munis.append(dict(id=ORDER.index(code), code=code, name=BY_CODE[code][0], n=len(m),
                          cx=round(float(m.x.median()), 1), cz=round(float(m.z.median()), 1),
                          span=round(float(max(x1 - x0, z1 - z0)), 1)))
    # whole area: the middle of the buildings' extent, wide enough to hold it (the capital alone when it is alone)
    x0, x1, z0, z1 = b.x.quantile(0.01), b.x.quantile(0.99), b.z.quantile(0.01), b.z.quantile(0.99)
    home = dict(cx=round(float((x0 + x1) / 2), 1), cz=round(float((z0 + z1) / 2), 1), span=float(max(x1 - x0, z1 - z0)))
    config = dict(
        city="sevilla", label=os.environ.get("SITE_LABEL") or (munis[0]["name"] if len(munis) == 1 else "Provincia de Sevilla"), tileSize=TILE, origin=GIRALDA,
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
