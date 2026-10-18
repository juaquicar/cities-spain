"""Municipios del proyecto: los 106 de la provincia de Sevilla, o los de la región elegida (pipeline/region.py).

Código = código INE de 5 cifras que usa el Catastro en su feed INSPIRE (provincia 41).
`carpeta` es el nombre exacto de la carpeta del feed (https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/41/).
El orden de la lista es el de la interfaz: primero Sevilla, después el resto por orden alfabético.
"""
from .region import REGION

SEVILLA = [
    ("41900", "Sevilla", "SEVILLA"),
    ("41001", "Aguadulce", "AGUADULCE"),
    ("41002", "Alanís", "ALANIS"),
    ("41003", "Albaida del Aljarafe", "ALBAIDA DEL ALJARAFE"),
    ("41004", "Alcalá de Guadaíra", "ALCALA DE GUADAIRA"),
    ("41005", "Alcalá del Río", "ALCALA DEL RIO"),
    ("41006", "Alcolea del Río", "ALCOLEA DEL RIO"),
    ("41008", "Algámitas", "ALGAMITAS"),
    ("41009", "Almadén de la Plata", "ALMADEN DE LA PLATA"),
    ("41010", "Almensilla", "ALMENSILLA"),
    ("41011", "Arahal", "ARAHAL"),
    ("41012", "Aznalcázar", "AZNALCAZAR"),
    ("41013", "Aznalcóllar", "AZNALCOLLAR"),
    ("41014", "Badolatosa", "BADOLATOSA"),
    ("41015", "Benacazón", "BENACAZON"),
    ("41016", "Bollullos de la Mitación", "BOLLULLOS DE LA MITACION"),
    ("41017", "Bormujos", "BORMUJOS"),
    ("41018", "Brenes", "BRENES"),
    ("41019", "Burguillos", "BURGUILLOS"),
    ("41021", "Camas", "CAMAS"),
    ("41103", "Cañada Rosal", "CAÑADA ROSAL"),
    ("41023", "Cantillana", "CANTILLANA"),
    ("41024", "Carmona", "CARMONA"),
    ("41025", "Carrión de los Céspedes", "CARRION DE LOS CESPEDES"),
    ("41026", "Casariche", "CASARICHE"),
    ("41027", "Castilblanco de los Arroyos", "CASTILBLANCO DE LOS ARROYOS"),
    ("41028", "Castilleja de Guzmán", "CASTILLEJA DE GUZMAN"),
    ("41029", "Castilleja de la Cuesta", "CASTILLEJA DE LA CUESTA"),
    ("41030", "Castilleja del Campo", "CASTILLEJA DEL CAMPO"),
    ("41032", "Cazalla de la Sierra", "CAZALLA DE LA SIERRA"),
    ("41033", "Constantina", "CONSTANTINA"),
    ("41034", "Coria del Río", "CORIA DEL RIO"),
    ("41035", "Coripe", "CORIPE"),
    ("41038", "Dos Hermanas", "DOS HERMANAS"),
    ("41039", "Écija", "ECIJA"),
    ("41031", "El Castillo de las Guardas", "EL CASTILLO DE LAS GUARDAS"),
    ("41036", "El Coronil", "EL CORONIL"),
    ("41105", "El Cuervo de Sevilla", "EL CUERVO DE SEVILLA"),
    ("41043", "El Garrobo", "EL GARROBO"),
    ("41057", "El Madroño", "EL MADROÑO"),
    ("41106", "El Palmar de Troya", "EL PALMAR DE TROYA"),
    ("41073", "El Pedroso", "EL PEDROSO"),
    ("41080", "El Real de la Jara", "EL REAL DE LA JARA"),
    ("41083", "El Ronquillo", "EL RONQUILLO"),
    ("41084", "El Rubio", "EL RUBIO"),
    ("41090", "El Saucejo", "EL SAUCEJO"),
    ("41102", "El Viso del Alcor", "EL VISO DEL ALCOR"),
    ("41040", "Espartinas", "ESPARTINAS"),
    ("41041", "Estepa", "ESTEPA"),
    ("41042", "Fuentes de Andalucía", "FUENTES DE ANDALUCIA"),
    ("41044", "Gelves", "GELVES"),
    ("41045", "Gerena", "GERENA"),
    ("41046", "Gilena", "GILENA"),
    ("41047", "Gines", "GINES"),
    ("41048", "Guadalcanal", "GUADALCANAL"),
    ("41049", "Guillena", "GUILLENA"),
    ("41050", "Herrera", "HERRERA"),
    ("41051", "Huévar del Aljarafe", "HUEVAR DEL ALJARAFE"),
    ("41104", "Isla Mayor", "ISLA MAYOR"),
    ("41007", "La Algaba", "LA ALGABA"),
    ("41022", "La Campana", "LA CAMPANA"),
    ("41056", "La Luisiana", "LA LUISIANA"),
    ("41077", "La Puebla de Cazalla", "LA PUEBLA DE CAZALLA"),
    ("41078", "La Puebla de los Infantes", "LA PUEBLA DE LOS INFANTES"),
    ("41079", "La Puebla del Río", "LA PUEBLA DEL RIO"),
    ("41081", "La Rinconada", "LA RINCONADA"),
    ("41082", "La Roda de Andalucía", "LA RODA DE ANDALUCIA"),
    ("41052", "Lantejuela", "LANTEJUELA"),
    ("41020", "Las Cabezas de San Juan", "LAS CABEZAS DE SAN JUAN"),
    ("41066", "Las Navas de la Concepción", "LAS NAVAS DE LA CONCEPCION"),
    ("41053", "Lebrija", "LEBRIJA"),
    ("41054", "Lora de Estepa", "LORA DE ESTEPA"),
    ("41055", "Lora del Río", "LORA DEL RIO"),
    ("41037", "Los Corrales", "LOS CORRALES"),
    ("41063", "Los Molares", "LOS MOLARES"),
    ("41069", "Los Palacios y Villafranca", "LOS PALACIOS Y VILLAFRANCA"),
    ("41058", "Mairena del Alcor", "MAIRENA DEL ALCOR"),
    ("41059", "Mairena del Aljarafe", "MAIRENA DEL ALJARAFE"),
    ("41060", "Marchena", "MARCHENA"),
    ("41061", "Marinaleda", "MARINALEDA"),
    ("41062", "Martín de la Jara", "MARTIN DE LA JARA"),
    ("41064", "Montellano", "MONTELLANO"),
    ("41065", "Morón de la Frontera", "MORON DE LA FRONTERA"),
    ("41067", "Olivares", "OLIVARES"),
    ("41068", "Osuna", "OSUNA"),
    ("41070", "Palomares del Río", "PALOMARES DEL RIO"),
    ("41071", "Paradas", "PARADAS"),
    ("41072", "Pedrera", "PEDRERA"),
    ("41074", "Peñaflor", "PEÑAFLOR"),
    ("41075", "Pilas", "PILAS"),
    ("41076", "Pruna", "PRUNA"),
    ("41085", "Salteras", "SALTERAS"),
    ("41086", "San Juan de Aznalfarache", "SAN JUAN DE AZNALFARACHE"),
    ("41088", "San Nicolás del Puerto", "SAN NICOLAS DEL PUERTO"),
    ("41087", "Sanlúcar la Mayor", "SANLUCAR LA MAYOR"),
    ("41089", "Santiponce", "SANTIPONCE"),
    ("41092", "Tocina", "TOCINA"),
    ("41093", "Tomares", "TOMARES"),
    ("41094", "Umbrete", "UMBRETE"),
    ("41095", "Utrera", "UTRERA"),
    ("41096", "Valencina de la Concepción", "VALENCINA DE LA CONCEPCION"),
    ("41097", "Villamanrique de la Condesa", "VILLAMANRIQUE DE LA CONDESA"),
    ("41100", "Villanueva de San Juan", "VILLANUEVA DE SAN JUAN"),
    ("41098", "Villanueva del Ariscal", "VILLANUEVA DEL ARISCAL"),
    ("41099", "Villanueva del Río y Minas", "VILLANUEVA DEL RIO Y MINAS"),
    ("41101", "Villaverde del Río", "VILLAVERDE DEL RIO"),
]

# La comarca del Aljarafe (sin la capital), para los sitios que la publican aparte
ALJARAFE = [
    "41003", "41010", "41012", "41013", "41015", "41016", "41017", "41021",
    "41025", "41028", "41029", "41030", "41034", "41040", "41044", "41047",
    "41051", "41059", "41067", "41070", "41075", "41079", "41085", "41086",
    "41087", "41089", "41093", "41094", "41096", "41097", "41098",
]

MUNICIPIOS = list(REGION.municipios) or SEVILLA
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
