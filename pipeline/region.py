"""The region the pipeline works on, from REGION (default `sevilla`): its data folder, frame and sources.

    REGION=madrid uv run python -m pipeline.build todos
    uv run python -m pipeline.sites madrid barcelona --deploy     # pipeline.sites sets REGION per site

Sevilla keeps its data in data/; any other region in data/<region>/. Each region has its own local frame (metres from
a landmark, in the UTM zone it lies in), its Catastro territorial office, its municipalities and its heritage source:
the IAPH in Andalucía, Wikidata elsewhere. Bizkaia and Gipuzkoa keep their own (foral) cadastres, each with its own INSPIRE feed.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Region:
    key: str
    crs: int                      # ETRS89 / UTM zone of the local frame
    landmark: tuple               # lon, lat of the frame's origin
    office: str                   # Catastro territorial office (feed folder)
    bbox: str                     # south, west, north, east: Overpass searches municipalities inside it
    label: str                    # page title when a site shows several municipalities
    heritage: str                 # "iaph" or "wikidata"
    wikidata: str = ""            # Wikidata item of the area, for heritage
    ine: dict = field(default_factory=dict)   # Catastro code → INE code, where they differ
    municipios: tuple = ()        # (code, name, feed folder); empty = the Sevilla list in municipios.py
    lidar_year: int = 2015
    cadastre: str = "dgc"         # "dgc" (Dirección General del Catastro), "bizkaia" or "gipuzkoa" (Diputaciones Forales)
    dem_crs: int = 25830          # frame of the IGN terrain model: UTM 30N, or REGCAN95 UTM 28N in Canarias


def city(key, crs, lon, lat, code, ine, name, folder, wikidata, **kw):
    """A one-municipality region: frame origin at the centre, Overpass box of ±0.15° around it."""
    return Region(key, crs, (lon, lat), code[:2], f"{lat - .15:.2f},{lon - .15:.2f},{lat + .15:.2f},{lon + .15:.2f}", name,
                  "wikidata", wikidata, ine={code: ine} if ine != code else {}, municipios=((code, name, folder),), **kw)


REGIONS = {
    "sevilla": Region("sevilla", 25830, (-5.99260, 37.38620), "41", "36.8,-6.6,38.25,-4.6", "Provincia de Sevilla",
                      "iaph", "Q95088",
                      ine={"41900": "41091", "41103": "41901", "41104": "41902", "41105": "41903", "41106": "41904"}),
    # Puerta del Sol, kilometre zero
    "madrid": Region("madrid", 25830, (-3.70358, 40.41670), "28", "40.25,-3.95,40.7,-3.5", "Madrid",
                     "wikidata", "Q2807", ine={"28900": "28079"}, municipios=(("28900", "Madrid", "MADRID"),)),
    # Plaça de Catalunya; Barcelona lies in UTM zone 31
    "barcelona": Region("barcelona", 25831, (2.17000, 41.38700), "08", "41.30,2.04,41.48,2.24", "Barcelona",
                        "wikidata", "Q1492", ine={"08900": "08019"}, municipios=(("08900", "Barcelona", "BARCELONA"),)),
    # Plaça de l'Ajuntament
    "valencia": Region("valencia", 25830, (-0.37660, 39.46990), "46", "39.27,-0.56,39.60,-0.27", "Valencia",
                       "wikidata", "Q8818", ine={"46900": "46250"}, municipios=(("46900", "Valencia", "VALENCIA"),)),
    # Plaza Mayor
    "salamanca": Region("salamanca", 25830, (-5.66390, 40.96500), "37", "40.90,-5.76,41.02,-5.58", "Salamanca",
                        "wikidata", "Q15695", ine={"37900": "37274"}, municipios=(("37900", "Salamanca", "SALAMANCA"),)),
    # Plaza del Pilar
    "zaragoza": Region("zaragoza", 25830, (-0.87830, 41.65620), "50", "41.45,-1.20,41.95,-0.65", "Zaragoza",
                       "wikidata", "Q10305", ine={"50900": "50297"}, municipios=(("50900", "Zaragoza", "ZARAGOZA"),)),
    # Teatro Arriaga; the foral cadastre numbers municipalities as the INE does
    "bilbao": Region("bilbao", 25830, (-2.92490, 43.25840), "48", "43.20,-3.00,43.30,-2.86", "Bilbao",
                     "wikidata", "Q8692", municipios=(("48020", "Bilbao", "BILBAO"),), cadastre="bizkaia"),
}

# the rest of the largest and most visited cities: (key, frame, centre, Catastro code and folder, INE, Wikidata)
CITIES = [
    ("malaga", 25830, -4.4214, 36.7213, "29900", "29067", "Málaga", "MALAGA", "Q8851"),
    ("murcia", 25830, -1.1307, 37.9922, "30030", "30030", "Murcia", "MURCIA", "Q12225"),
    ("palma", 25831, 2.6502, 39.5696, "07040", "07040", "Palma", "PALMA", "Q8826"),
    ("las-palmas", 4083, -15.4363, 28.1235, "35017", "35016", "Las Palmas de Gran Canaria", "LAS PALMAS DE GRAN CANARIA",
     "Q11974"),
    ("alicante", 25830, -0.4810, 38.3452, "03900", "03014", "Alicante", "ALICANTE ALACANT", "Q11959"),
    ("granada", 25830, -3.5986, 37.1773, "18900", "18087", "Granada", "GRANADA", "Q8810"),
    ("benidorm", 25830, -0.1225, 38.5411, "03031", "03031", "Benidorm", "BENIDORM", "Q487981"),
    ("cordoba", 25830, -4.7794, 37.8882, "14900", "14021", "Córdoba", "CORDOBA", "Q5818"),
    ("toledo", 25830, -4.0273, 39.8628, "45900", "45168", "Toledo", "TOLEDO", "Q5836"),
    ("santiago", 25829, -8.5448, 42.8782, "15079", "15078", "Santiago de Compostela", "SANTIAGO DE COMPOSTELA", "Q14314"),
    ("segovia", 25830, -4.1088, 40.9429, "40900", "40194", "Segovia", "SEGOVIA", "Q15684"),
    ("merida", 25830, -6.3437, 38.9161, "06083", "06083", "Mérida", "MERIDA", "Q14323"),
    ("avila", 25830, -4.6818, 40.6565, "05900", "05019", "Ávila", "AVILA", "Q15688"),
    ("alcala-de-henares", 25830, -3.3643, 40.4818, "28005", "28005", "Alcalá de Henares", "ALCALA DE HENARES", "Q46940"),
    ("baeza", 25830, -3.4708, 37.9936, "23009", "23009", "Baeza", "BAEZA", "Q488555"),
    ("caceres", 25830, -6.3724, 39.4753, "10900", "10037", "Cáceres", "CACERES", "Q15678"),
    ("cuenca", 25830, -2.1374, 40.0704, "16900", "16078", "Cuenca", "CUENCA", "Q15098"),
    ("ibiza", 25831, 1.4206, 38.9067, "07026", "07026", "Ibiza", "EIVISSA", "Q473914"),
    ("la-laguna", 4083, -16.3159, 28.4874, "38023", "38023", "San Cristóbal de La Laguna", "SAN CRISTOBAL DE LA LAGUNA",
     "Q54898"),
    ("tarragona", 25831, 1.2445, 41.1189, "43900", "43148", "Tarragona", "TARRAGONA", "Q15088"),
    ("ubeda", 25830, -3.3705, 38.0133, "23092", "23092", "Úbeda", "UBEDA", "Q329984"),
]
# Gipuzkoa keeps its own foral cadastre too, in one INSPIRE file for the whole province
REGIONS["san-sebastian"] = city("san-sebastian", 25830, -1.9812, 43.3183, "20069", "20069", "San Sebastián", "DONOSTIA",
                                "Q10313", cadastre="gipuzkoa")
for key, crs, lon, lat, code, ine, name, folder, wd in CITIES:
    REGIONS[key] = city(key, crs, lon, lat, code, ine, name, folder, wd, dem_crs=4083 if crs == 4083 else 25830)

REGION = REGIONS[os.environ.get("REGION", "sevilla")]
DATA = Path("data") if REGION.key == "sevilla" else Path("data") / REGION.key
