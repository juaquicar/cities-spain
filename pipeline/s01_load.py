"""Catastro GML → one row per building (data/buildings.parquet) and its parts by floors (data/parts.parquet).

Everything is reprojected to the region's UTM zone (Sevilla and Madrid 30N, Barcelona 31N): the Catastro serves Sevilla
province in zone 29 or 30 depending on the office, and the city sits on the boundary between them.
"""
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

from .s00_fetch_catastro import RAW, chosen
from .municipios import BY_CODE, ORDER
from .region import DATA, REGION

CRS = REGION.crs
B_COLS = ["localId", "beginning", "currentUse", "numberOfDwellings", "numberOfBuildingUnits",
          "conditionOfConstruction", "value"]
P_COLS = ["localId", "numberOfFloorsAboveGround", "numberOfFloorsBelowGround"]


# Bizkaia's INSPIRE uses → the Catastro's codes, which s02 reads
BIZKAIA_USE = {"residential": "1_residential", "agriculture": "2_agriculture", "industrial": "3_industrial",
               "office": "4_1_office", "retail": "4_2_retail", "publicServices": "4_3_publicServices"}


def load_bizkaia(code: str):
    """The foral cadastre gives buildings only (no parts): each building is its own single part. Its uses repeat up to
    three times per building, mostly empty, which GDAL's flattening loses; they are read from the GML text."""
    gml = RAW / code / "ES.BFA.BU.gml"
    b = pyogrio.read_dataframe(gml, layer="Building", columns=["reference", "end", "numberOfDwellings",
                                                               "numberOfBuildingUnits", "numberOfFloorsAboveGround"])
    text = gml.read_text(encoding="utf-8", errors="replace")
    use, cond = {}, {}
    for block in text.split('<bu-core2d:Building gml:id="')[1:]:
        gid = block[:block.index('"')]
        u = re.search(r'<bu-base:currentUse xlink:title="\s*(\w+)\s*"', block)
        c = re.search(r'conditionOfConstruction xlink:title="\s*(\w+)\s*"', block)
        use[gid], cond[gid] = (BIZKAIA_USE.get(u.group(1), "") if u else ""), (c.group(1) if c else "")
    ids = pyogrio.read_dataframe(gml, layer="Building", columns=["gml_id"], read_geometry=False).gml_id
    b = b.to_crs(CRS).rename(columns={"reference": "localId"})
    b["currentUse"] = ids.map(use).to_numpy()
    b["conditionOfConstruction"] = ids.map(cond).to_numpy()
    b["beginning"] = b.pop("end").astype(str)
    b["value"] = np.nan
    b["muni"] = ORDER.index(code)
    p = b[["localId", "numberOfFloorsAboveGround", "geometry"]].copy()
    p["numberOfFloorsBelowGround"] = np.nan
    p["ref"] = p.localId
    return b.drop(columns="numberOfFloorsAboveGround"), p


# Gipuzkoa's INSPIRE uses → the Catastro's codes
GIPUZKOA_USE = {"residence": "1_residential", "individualResidence": "1_residential", "collectiveResidence": "1_residential",
                "agriculture": "2_agriculture", "industrial": "3_industrial", "commerceAndServices": "4_commerceAndServices",
                "office": "4_1_office", "trade": "4_2_retail", "publicServices": "4_3_publicServices"}


def gipuzkoa_buildings(gml, muni: str):
    """Stream the province's GML (1 GB) and yield the buildings of one municipality (its three-digit foral number)."""
    tag, buf = "<bu-ext2d:Building ", ""
    with open(gml, encoding="utf-8", errors="replace") as f:
        while chunk := f.read(1 << 24):
            buf += chunk
            blocks = buf.split(tag)
            buf = blocks.pop()
            for block in blocks:
                if f"ES.GFA.CP.{muni}-" in block:
                    yield block
        if f"ES.GFA.CP.{muni}-" in buf:
            yield buf


def ring(pos: str):
    v = np.array(pos.split(), float).reshape(-1, 2)
    return v[:, ::-1]  # EPSG:3042 lists northing first


def load_gipuzkoa(code: str):
    """The foral cadastre gives buildings only, with year, use and floors; each building is its own single part. Its
    reference (7 digits) names the parcel, which several buildings may share, so the building's own number follows it."""
    from shapely.geometry import Polygon
    rows = []
    for block in gipuzkoa_buildings(RAW / code / "ES.GFA.BU.gml", code[2:]):
        get = lambda pat: (m.group(1) if (m := re.search(pat, block)) else None)
        poly = re.search(r"<gml:Polygon.*?</gml:Polygon>", block, re.S)
        if not poly:
            continue
        ext = re.search(r"<gml:exterior>.*?<gml:posList[^>]*>([^<]+)", poly.group(0), re.S)
        holes = re.findall(r"<gml:interior>.*?<gml:posList[^>]*>([^<]+)", poly.group(0), re.S)
        use = get(r'CurrentUseValue/(\w+)"')
        rows.append(dict(localId=f'{get(r"<bu-base:reference>(\d+)")}-{get(r"<base:localId>(\d+)")}',
                         beginning=get(r"<bu-base:end>(\d{4})") or "",
                         currentUse=GIPUZKOA_USE.get(use, "") if use else "",
                         numberOfDwellings=float(get(r"numberOfDwellings[^>]*>(\d+)") or "nan"),
                         numberOfBuildingUnits=np.nan,
                         conditionOfConstruction=get(r"ConditionOfConstructionValue/(\w+)") or "",
                         numberOfFloorsAboveGround=float(get(r"numberOfFloorsAboveGround[^>]*>(\d+)") or "nan"),
                         numberOfFloorsBelowGround=float(get(r"numberOfFloorsBelowGround[^>]*>(\d+)") or "nan"),
                         geometry=Polygon(ring(ext.group(1)), [ring(h) for h in holes])))
    b = gpd.GeoDataFrame(rows, crs=3042).to_crs(CRS)
    b["value"] = np.nan
    b["muni"] = ORDER.index(code)
    p = b[["localId", "numberOfFloorsAboveGround", "numberOfFloorsBelowGround", "geometry"]].copy()
    p["ref"] = p.localId
    return b.drop(columns=["numberOfFloorsAboveGround", "numberOfFloorsBelowGround"]), p


def load(code: str):
    if REGION.cadastre == "bizkaia":
        return load_bizkaia(code)
    if REGION.cadastre == "gipuzkoa":
        return load_gipuzkoa(code)
    base = RAW / code / f"A.ES.SDGC.BU.{code}."
    b = pyogrio.read_dataframe(f"{base}building.gml", layer="Building", columns=B_COLS)
    p = pyogrio.read_dataframe(f"{base}buildingpart.gml", layer="BuildingPart", columns=P_COLS)
    b, p = b.to_crs(CRS), p.to_crs(CRS)
    # pyogrio types the date as text or as a timestamp depending on the file; s02 reads its first four characters
    b["beginning"] = b.beginning.astype(str)
    b["muni"] = ORDER.index(code)
    p["ref"] = p.localId.str.split("_").str[0]
    return b, p


def main():
    bs, ps = [], []
    for code in chosen():
        b, p = load(code)
        print(f"  {BY_CODE[code][0]}: {len(b)} edificios, {len(p)} partes")
        bs.append(b); ps.append(p)
    b = gpd.GeoDataFrame(pd.concat(bs, ignore_index=True), crs=CRS).rename(columns={"localId": "ref"})
    p = gpd.GeoDataFrame(pd.concat(ps, ignore_index=True), crs=CRS)
    b = b[~b.geometry.is_empty & b.geometry.notna()].drop_duplicates("ref")
    # ruins stay out: the Catastro keeps them, the city does not show them
    b = b[b.conditionOfConstruction != "ruin"]
    p = p[p.ref.isin(b.ref) & ~p.geometry.is_empty & p.geometry.notna()]
    b.to_parquet(DATA / "buildings_raw.parquet"); p.to_parquet(DATA / "parts.parquet")
    print(len(b), "edificios;", len(p), "partes")


if __name__ == "__main__":
    main()
