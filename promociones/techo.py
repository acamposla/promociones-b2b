"""Techo de descuento por grupo y rentabilidad de un rappel condicional.

El rappel: "si me compras un u % más de lo que ya me compras, te descuento un d %
solo sobre lo que crezcas". Para un grupo de volumen V y margen ponderado m, si una
parte r de los clientes acepta y cumple:

    neto = r · u · V · (m − d)

Con d = m el neto es cero sea cual sea r. La tasa de respuesta decide cuánto se gana;
el descuento decide si se gana. Por eso el techo (d = m) se calcula sin ningún dato de
campañas, solo con la facturación.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ORDEN = ["Premium", "Commodity", "Emergentes", "Masa"]


def margen_ponderado(g: pd.DataFrame) -> float:
    """Margen % del grupo pesado por volumen: el punto donde la campaña deja de ganar."""
    return float(np.average(g.margen_pct, weights=g.volumen))


def techo_por_segmento(abt: pd.DataFrame, segmento: pd.Series) -> pd.DataFrame:
    """Techo (margen ponderado), suelo seguro (p25 del margen) y peso en el volumen."""
    d = abt.assign(segmento=segmento)
    g = d.groupby("segmento")
    out = pd.DataFrame({
        "clientes": g.size(),
        "techo": g.apply(margen_ponderado),
        "suelo_p25": g.margen_pct.quantile(0.25),
        "dispersion_margen": g.margen_pct.std(),
        "pct_volumen": g.volumen.sum() / d.volumen.sum(),
    })
    return out.reindex([s for s in ORDEN if s in out.index])


def bajo_el_agua(abt: pd.DataFrame, segmento: pd.Series, d: float) -> pd.Series:
    """Parte de los clientes de cada grupo cuyo margen propio es menor que el descuento d."""
    return (abt.margen_pct < d).groupby(segmento).mean().reindex(ORDEN)


def neto_rappel(volumen: float, margen: float, d: float, u: float, r: float) -> float:
    """Neto del rappel por crecimiento para un grupo (ver el docstring del módulo)."""
    return r * u * volumen * (margen - d)


def escenarios(abt: pd.DataFrame, segmento: pd.Series, grupo: str, u: float = 0.06,
               descuentos=(0.04, 0.08, 0.12, 0.16),
               respuestas=(0.15, 0.30, 0.45, 0.60)) -> pd.DataFrame:
    """Matriz descuento × aceptación con el neto del rappel para un grupo."""
    s = abt[segmento == grupo]
    v, m = s.volumen.sum(), margen_ponderado(s)
    return pd.DataFrame(
        {f"r={r:.0%}": [neto_rappel(v, m, d, u, r) for d in descuentos] for r in respuestas},
        index=[f"d={d:.0%}" for d in descuentos])


def rejilla(abt: pd.DataFrame, segmento: pd.Series, desc_min: float = 0.06,
            vol_min: float = 2_000.0) -> pd.DataFrame:
    """Acción por segmento y cuartil de volumen, con umbrales que decide negocio.

    desc_min: por debajo de este techo no queda hueco para una oferta de precio.
    vol_min:  con un volumen mediano menor, el coste de gestionar la promoción no compensa.
    """
    filas = []
    for seg in ORDEN:
        s = abt[segmento == seg].copy()
        s["cuartil"] = pd.qcut(s.volumen.rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
        for q, g in s.groupby("cuartil", observed=True):
            t, vm = margen_ponderado(g), g.volumen.median()
            if t < desc_min:
                accion = "Sin descuento de precio: palanca de servicio o plazos"
            elif vm < vol_min:
                accion = "Solo acción de coste casi nulo (digital)"
            else:
                accion = "Promoción de precio viable"
            filas.append({"segmento": seg, "cuartil": q, "clientes": len(g), "techo": t,
                          "volumen_mediano": vm, "accion": accion})
    return pd.DataFrame(filas)
