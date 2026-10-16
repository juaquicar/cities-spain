"""Municipios del proyecto: Sevilla capital y la comarca del Aljarafe.

Código = código INE de 5 cifras que usa el Catastro en su feed INSPIRE (provincia 41).
`carpeta` es el nombre exacto de la carpeta del feed (https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/41/).
El orden de la lista es el de la interfaz: primero Sevilla, después el Aljarafe por orden alfabético.
"""

MUNICIPIOS = [
    ("41900", "Sevilla", "SEVILLA"),
    ("41003", "Albaida del Aljarafe", "ALBAIDA DEL ALJARAFE"),
    ("41010", "Almensilla", "ALMENSILLA"),
    ("41012", "Aznalcázar", "AZNALCAZAR"),
    ("41013", "Aznalcóllar", "AZNALCOLLAR"),
    ("41015", "Benacazón", "BENACAZON"),
    ("41016", "Bollullos de la Mitación", "BOLLULLOS DE LA MITACION"),
    ("41017", "Bormujos", "BORMUJOS"),
    ("41021", "Camas", "CAMAS"),
    ("41025", "Carrión de los Céspedes", "CARRION DE LOS CESPEDES"),
    ("41028", "Castilleja de Guzmán", "CASTILLEJA DE GUZMAN"),
    ("41029", "Castilleja de la Cuesta", "CASTILLEJA DE LA CUESTA"),
    ("41030", "Castilleja del Campo", "CASTILLEJA DEL CAMPO"),
    ("41034", "Coria del Río", "CORIA DEL RIO"),
    ("41040", "Espartinas", "ESPARTINAS"),
    ("41044", "Gelves", "GELVES"),
    ("41047", "Gines", "GINES"),
    ("41051", "Huévar del Aljarafe", "HUEVAR DEL ALJARAFE"),
    ("41059", "Mairena del Aljarafe", "MAIRENA DEL ALJARAFE"),
    ("41067", "Olivares", "OLIVARES"),
    ("41070", "Palomares del Río", "PALOMARES DEL RIO"),
    ("41075", "Pilas", "PILAS"),
    ("41079", "La Puebla del Río", "LA PUEBLA DEL RIO"),
    ("41085", "Salteras", "SALTERAS"),
    ("41086", "San Juan de Aznalfarache", "SAN JUAN DE AZNALFARACHE"),
    ("41087", "Sanlúcar la Mayor", "SANLUCAR LA MAYOR"),
    ("41089", "Santiponce", "SANTIPONCE"),
    ("41093", "Tomares", "TOMARES"),
    ("41094", "Umbrete", "UMBRETE"),
    ("41096", "Valencina de la Concepción", "VALENCINA DE LA CONCEPCION"),
    ("41097", "Villamanrique de la Condesa", "VILLAMANRIQUE DE LA CONDESA"),
    ("41098", "Villanueva del Ariscal", "VILLANUEVA DEL ARISCAL"),
]

BY_CODE = {c: (n, f) for c, n, f in MUNICIPIOS}
ORDER = [c for c, _, _ in MUNICIPIOS]


def resolve(args):
    """Accepts codes or (partial, accent-free) names: `41093`, `tomares`, `sevilla`, `todos`."""
    import unicodedata
    plain = lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    out = []
    for a in args:
        if plain(a) in ("todos", "all"):
            return list(ORDER)
        if a in BY_CODE:
            out.append(a); continue
        hits = [c for c, n, _ in MUNICIPIOS if plain(a) == plain(n)] or \
               [c for c, n, _ in MUNICIPIOS if plain(a) in plain(n)]
        if len(hits) != 1:
            raise SystemExit(f"Municipio ambiguo o desconocido: {a!r} → {[BY_CODE[h][0] for h in hits]}")
        out.append(hits[0])
    return sorted(set(out), key=ORDER.index)
