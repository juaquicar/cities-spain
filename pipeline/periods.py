"""Periodos históricos de cada región: (clave, etiqueta, desde, hasta, color).

Los colores van de los ocres y tierras de lo antiguo a los azules de lo reciente; cada región usa los mismos diez.
"""
from .region import REGION

COLORS = ["#5b2a1a", "#8c3b1f", "#b5532a", "#d27a2c", "#e2a737", "#c9c14a", "#83b06a", "#3f9c8f", "#2f6fa8", "#3a3f8f"]

LABELS = {
    "sevilla": [
        ("medieval", "Al-Ándalus y Baja Edad Media", -200, 1499),
        ("indias", "Siglo de Oro, Carrera de Indias", 1500, 1699),
        ("barroco", "Barroco tardío e Ilustración", 1700, 1799),
        ("xix", "Siglo XIX", 1800, 1899),
        ("regionalismo", "Regionalismo y Expo 1929", 1900, 1931),
        ("posguerra", "República, guerra y posguerra", 1932, 1959),
        ("desarrollismo", "Desarrollismo", 1960, 1975),
        ("transicion", "Transición, camino a la Expo 92", 1976, 1992),
        ("boom", "Boom inmobiliario", 1993, 2007),
        ("reciente", "Crisis y después", 2008, 2100),
    ],
    "madrid": [
        ("medieval", "Mayrit y la villa medieval", -200, 1560),
        ("austrias", "Corte de los Austrias", 1561, 1700),
        ("borbones", "Borbones e Ilustración", 1701, 1807),
        ("xix", "Siglo XIX y Ensanche", 1808, 1899),
        ("granvia", "Gran Vía y entreguerras", 1900, 1935),
        ("posguerra", "Guerra y posguerra", 1936, 1959),
        ("desarrollismo", "Desarrollismo", 1960, 1975),
        ("transicion", "Transición y Movida", 1976, 1992),
        ("boom", "Boom inmobiliario", 1993, 2007),
        ("reciente", "Crisis y después", 2008, 2100),
    ],
    "barcelona": [
        ("medieval", "Barcino y la ciudad medieval", -200, 1499),
        ("moderna", "Edad Moderna", 1500, 1813),
        ("xix", "Industria y derribo de las murallas", 1814, 1859),
        ("cerda", "Eixample de Cerdà", 1860, 1887),
        ("modernisme", "Modernisme y Expo 1929", 1888, 1931),
        ("posguerra", "República, guerra y posguerra", 1932, 1959),
        ("desarrollismo", "Desarrollismo", 1960, 1975),
        ("transicion", "Transición, camino a los Juegos del 92", 1976, 1992),
        ("boom", "Fòrum y boom inmobiliario", 1993, 2007),
        ("reciente", "Crisis y después", 2008, 2100),
    ],
}

PERIODS = [(k, l, a, b, c) for (k, l, a, b), c in zip(LABELS[REGION.key], COLORS)]


def period_of(year: int) -> int:
    for i, (_, _, a, b, _) in enumerate(PERIODS):
        if a <= year <= b:
            return i
    return 0 if year < PERIODS[0][2] else len(PERIODS) - 1
