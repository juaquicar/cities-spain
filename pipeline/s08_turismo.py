"""What to see: the area's best-known places from Wikidata, and the stops of the themed walks (pipeline/rutas.json).

Fame is the number of Wikipedia editions with an article on the item (Wikidata sitelinks): the Museo del Prado has 80,
a parish church 2. Items that are not places to visit (clubs, companies, events, universities as institutions, the
city itself) are left out by their type. A place sits on the building under its point (or the nearest within NEAR
metres); squares, parks, bridges and gates stand on their own point.

Output: data[/region]/turismo.parquet, one row per Wikidata item: wd, name, desc, sl, wp, img, ref (building, may be
empty), x, y (region frame), lon, lat. s03_tiles picks each site's share and writes turismo.json.
"""
import json
import re
from pathlib import Path
from urllib.parse import unquote

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from .region import DATA, REGION
from .s05_monumentos import CACHE, WIKIDATA, get

MIN_SITELINKS = 4
NEAR = 40.0
ROUTES = Path(__file__).with_name("rutas.json")
NOT_A_PLACE = re.compile(
    r"organizaci|empresa|compañía|club|equipo|evento|torneo|competición|campeonato|accidente|vuelo|batalla|atentado|"
    r"masacre|universidad|escuela|instituto|institución|fundación|banco|aeropuerto|ciudad|capital|municipio|distrito|"
    r"barrio|línea|ferrocarril|autopista|autovía|carretera|río|ser humano|partido|sindicato|periódico|festival|feria|"
    r"exposición|edición|elecciones|tratado|agencia|ministerio|organismo|asociación|academia|orquesta|cofradía|"
    r"hermandad|diócesis|archidiócesis|provincia|comarca|área metropolitana|desaparecid|demolid|ya no existe|"
    r"sede|hotel|tienda|restaurante|centro comercial|hospital|cárcel|prisión|cuartel|base aérea|estación|parada|"
    r"empresa|marca|programa|serie|película|obra literaria|canción|álbum|juicio|proceso|ciudad deportiva|metro|"
    r"tranvía|red de|sistema de|servicio", re.I)
# venues with many Wikipedias for their teams, not for the building: they count for less
SPORT = re.compile(r"estadio|campo de fútbol|pabellón|palacio de deportes|arena|recinto deportivo|velódromo|hipódromo", re.I)
SPORT_WEIGHT = 0.3
# places a visitor walks to that are not buildings: they keep their own point
OPEN_PLACE = re.compile(r"plaza|parque|jardín|puente|puerta|arco|fuente|mirador|paseo|alameda|glorieta|monumento|"
                        r"muralla|calle|playa|estanque|lago|acueducto|teatro romano|anfiteatro|yacimiento", re.I)
BUILDING = re.compile(r"iglesia|catedral|basílica|capilla|ermita|palacio|museo|edificio|convento|monasterio|teatro|"
                      r"torre|casa|castillo|alcázar|estadio|mercado|ayuntamiento|rascacielos|plaza de toros", re.I)


def routes():
    return json.loads(ROUTES.read_text()).get(REGION.key, []) if ROUTES.exists() else []


def query():
    """Famous items of the area, plus every stop of its walks whatever its fame."""
    stops = sorted({s["wd"] for r in routes() for s in r["stops"]})
    f = CACHE / f"famous2_{REGION.wikidata}_{len(stops)}.json"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        values = " ".join(f"wd:{q}" for q in stops)
        q = """SELECT ?item ?itemLabel ?itemDescription ?coord ?sl ?art ?img (GROUP_CONCAT(DISTINCT ?tl; separator="|") AS ?types)
        (SAMPLE(?gone) AS ?end)
        WHERE {
          { ?item wdt:P131* wd:%s ; wikibase:sitelinks ?sl . FILTER(?sl >= %d) }
          %s
          ?item wdt:P625 ?coord ; wikibase:sitelinks ?sl .
          OPTIONAL { ?item wdt:P31 ?t . ?t rdfs:label ?tl FILTER(lang(?tl) = "es") }
          OPTIONAL { ?item wdt:P18 ?img }
          OPTIONAL { ?item wdt:P576 ?gone }
          OPTIONAL { ?art schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "es,ca,eu,gl,en". }
        } GROUP BY ?item ?itemLabel ?itemDescription ?coord ?sl ?art ?img""" % (
            REGION.wikidata, MIN_SITELINKS, f"UNION {{ VALUES ?item {{ {values} }} }}" if stops else "")
        f.write_text(get(WIKIDATA, params=dict(query=q, format="json")).text)
    return json.loads(f.read_text())["results"]["bindings"], set(stops)


def main():
    rows, stops = query()
    items = {}
    for b in rows:
        v = lambda k: b.get(k, {}).get("value", "")
        qid, pt = v("item").rsplit("/", 1)[-1], v("coord")
        if not pt.startswith("Point(") or qid in items:
            continue
        types = v("types")
        # demolished (Wikidata end date), or a whole quarter: nothing to label on a roof
        if qid not in stops and (v("end") or re.search(r"barrio|distrito|circuito", types)
                                 or re.search(r"derribad|demolid|desaparecid", v("itemDescription"), re.I)):
            continue
        # a museum is also an "organización" and the Reina Sofía a "hospital clausurado": a place type wins
        placeish = BUILDING.search(types) or OPEN_PLACE.search(types) or "turístic" in types
        if qid not in stops and ((NOT_A_PLACE.search(types) and not placeish) or v("itemLabel") == qid):
            continue
        sl = int(v("sl"))
        items[qid] = dict(wd=qid, name=re.sub(r"\s*\([^)]*\)$", "", v("itemLabel")), desc=v("itemDescription"), sl=sl,
                          score=sl * (SPORT_WEIGHT if SPORT.search(types) else 1.0),
                          wp=v("art"), img=unquote(v("img").rsplit("/", 1)[-1]),
                          open=bool(OPEN_PLACE.search(types)) and not BUILDING.search(types) or
                               (qid in stops and bool(re.search("barrio|judería", types))),  # a quarter on a walk
                          geometry=Point(map(float, pt[6:-1].split())))
    m = gpd.GeoDataFrame(list(items.values()), crs=4326)
    m["lon"], m["lat"] = m.geometry.x, m.geometry.y
    m = m.to_crs(REGION.crs)
    b = gpd.read_parquet(DATA / "buildings.parquet")[["ref", "geometry"]]
    hit = gpd.sjoin(m, b, predicate="within", how="left").drop(columns="index_right")
    hit = hit[~hit.index.duplicated()]
    # a square's point often falls on a kiosk or a fountain: open places keep their point
    hit.loc[hit.open, "ref"] = None
    miss = hit[hit.ref.isna() & ~hit.open].drop(columns="ref")
    near = gpd.sjoin_nearest(miss, b, max_distance=NEAR, how="left").drop(columns="index_right")
    near = near[~near.index.duplicated()]
    hit.loc[near.index, "ref"] = near.ref
    # neither on a building nor an open place: nothing to show it on, unless it is a stop of a walk
    keep = hit.ref.notna() | hit.open | hit.wd.isin(stops)
    out = hit[keep].copy()
    out["x"], out["y"] = out.geometry.x, out.geometry.y
    out = pd.DataFrame(out.drop(columns=["geometry", "open"])).sort_values("score", ascending=False)
    out.to_parquet(DATA / "turismo.parquet")
    print(f"{len(out)} lugares conocidos ({int(out.ref.notna().sum())} en un edificio); "
          f"rutas: {len(routes())}, paradas sin lugar: {sorted(stops - set(out.wd))}")


if __name__ == "__main__":
    main()
