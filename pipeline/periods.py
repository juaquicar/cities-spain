"""Periodos históricos de Sevilla y su entorno: (clave, etiqueta, desde, hasta, color).

Los colores van de los ocres y tierras de lo antiguo a los azules de lo reciente.
"""

PERIODS = [
    ("medieval", "Al-Ándalus y Baja Edad Media", -200, 1499, "#5b2a1a"),
    ("indias", "Siglo de Oro, Carrera de Indias", 1500, 1699, "#8c3b1f"),
    ("barroco", "Barroco tardío e Ilustración", 1700, 1799, "#b5532a"),
    ("xix", "Siglo XIX", 1800, 1899, "#d27a2c"),
    ("regionalismo", "Regionalismo y Expo 1929", 1900, 1931, "#e2a737"),
    ("posguerra", "República, guerra y posguerra", 1932, 1959, "#c9c14a"),
    ("desarrollismo", "Desarrollismo", 1960, 1975, "#83b06a"),
    ("transicion", "Transición, camino a la Expo 92", 1976, 1992, "#3f9c8f"),
    ("boom", "Boom inmobiliario", 1993, 2007, "#2f6fa8"),
    ("reciente", "Crisis y después", 2008, 2100, "#3a3f8f"),
]


def period_of(year: int) -> int:
    for i, (_, _, a, b, _) in enumerate(PERIODS):
        if a <= year <= b:
            return i
    return 0 if year < PERIODS[0][2] else len(PERIODS) - 1
