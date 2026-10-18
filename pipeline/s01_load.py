"""Catastro GML → one row per building (data/buildings.parquet) and its parts by floors (data/parts.parquet).

Everything is reprojected to the region's UTM zone (Sevilla and Madrid 30N, Barcelona 31N): the Catastro serves Sevilla
province in zone 29 or 30 depending on the office, and the city sits on the boundary between them.
"""
import geopandas as gpd
import pandas as pd
import pyogrio

from .s00_fetch_catastro import RAW, chosen
from .municipios import BY_CODE, ORDER
from .region import DATA, REGION

CRS = REGION.crs
B_COLS = ["localId", "beginning", "currentUse", "numberOfDwellings", "numberOfBuildingUnits",
          "conditionOfConstruction", "value"]
P_COLS = ["localId", "numberOfFloorsAboveGround", "numberOfFloorsBelowGround"]


def load(code: str):
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
