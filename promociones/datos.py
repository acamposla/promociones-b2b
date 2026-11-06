"""Líneas de factura sintéticas de un distribuidor B2B ficticio.

Todo lo que sale de aquí es inventado. El generador imita la forma de una cartera B2B
real (cola larga de volumen, margen independiente del tamaño, un grupo pequeño que
crece deprisa), no sus cifras. Los parámetros de cada arquetipo están elegidos a mano
para que se cumplan cuatro órdenes cualitativos:

- volumen total del grupo:  Commodity > Premium > Emergentes > Masa
- volumen medio por cliente: Premium > Commodity
- margen (techo de descuento): Premium > Masa > Emergentes > Commodity
- Commodity concentra su volumen en pocos clientes muy grandes

El arquetipo de cada cliente NO sale en las facturas: el clustering tiene que
encontrarlo por su cuenta.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SEMILLA = 2026
ANIO = 2025  # año de análisis; las facturas cubren también el anterior
N_CATEGORIAS = 12


@dataclass(frozen=True)
class Arquetipo:
    n: int                   # clientes
    vol_mediana: float       # volumen anual mediano, en €
    vol_sigma: float         # dispersión log-normal del volumen
    pedidos_mediana: float   # pedidos al año
    margen: float            # margen medio sobre venta
    margen_sd: float         # dispersión del margen entre clientes
    categorias: tuple        # rango de categorías que compra (mín, máx)
    crecimiento: float       # volumen de este año / el anterior, mediana
    crecimiento_sd: float    # dispersión log-normal del crecimiento
    pct_nuevos: float        # clientes sin compras el año anterior


ARQUETIPOS: dict[str, Arquetipo] = {
    "Commodity": Arquetipo(345, 150_000, 1.40, 60, 0.080, 0.050, (2, 6), 1.00, 0.18, 0.00),
    "Premium": Arquetipo(190, 345_000, 0.85, 66, 0.310, 0.080, (6, 12), 1.03, 0.15, 0.00),
    "Emergentes": Arquetipo(100, 45_000, 1.00, 25, 0.160, 0.070, (2, 6), 2.00, 0.25, 0.30),
    "Masa": Arquetipo(650, 12_000, 1.15, 10, 0.200, 0.100, (1, 5), 0.95, 0.22, 0.00),
}


def _lineas_de_un_anio(rng, cliente, anio, volumen, pedidos, cats, margen):
    """Reparte el volumen de un año en pedidos y líneas, con margen por línea."""
    pesos = rng.dirichlet(np.ones(pedidos))
    dias = rng.integers(0, 365, pedidos)
    filas = []
    for p, (peso, dia) in enumerate(zip(pesos, dias)):
        n_lineas = int(rng.integers(1, 4))
        reparto = rng.dirichlet(np.ones(n_lineas))
        for parte in reparto:
            importe = round(volumen * peso * parte, 2)
            if importe <= 0:
                continue
            m = float(np.clip(margen + rng.normal(0, 0.02), -0.3, 0.7))
            filas.append((
                f"{cliente}-{anio}-{p:03d}",
                cliente,
                (pd.Timestamp(f"{anio}-01-01") + pd.Timedelta(days=int(dia))).date().isoformat(),
                f"cat_{int(rng.choice(cats)):02d}",
                importe,
                round(importe * (1 - m), 2),
            ))
    return filas


def generar_facturas(semilla: int = SEMILLA, anio: int = ANIO) -> pd.DataFrame:
    """Devuelve una fila por línea de factura de los años `anio - 1` y `anio`.

    Columnas: pedido, cliente, fecha, categoria, importe, coste.
    """
    rng = np.random.default_rng(semilla)
    filas = []
    contador = 0
    for a in ARQUETIPOS.values():
        for _ in range(a.n):
            contador += 1
            cliente = f"C{contador:04d}"
            vol = float(rng.lognormal(np.log(a.vol_mediana), a.vol_sigma))
            pedidos = max(1, int(rng.poisson(a.pedidos_mediana)))
            margen = float(np.clip(rng.normal(a.margen, a.margen_sd), -0.2, 0.65))
            n_cat = int(rng.integers(a.categorias[0], a.categorias[1] + 1))
            cats = rng.choice(np.arange(1, N_CATEGORIAS + 1), n_cat, replace=False)
            filas += _lineas_de_un_anio(rng, cliente, anio, vol, pedidos, cats, margen)

            if rng.random() >= a.pct_nuevos:  # cliente que ya compraba el año anterior
                crec = float(rng.lognormal(np.log(a.crecimiento), a.crecimiento_sd))
                ped_ant = max(1, int(rng.poisson(a.pedidos_mediana / max(crec, 0.5))))
                filas += _lineas_de_un_anio(rng, cliente, anio - 1, vol / crec, ped_ant,
                                            cats, margen)

    # El orden de las filas no debe delatar el arquetipo.
    df = pd.DataFrame(filas, columns=["pedido", "cliente", "fecha", "categoria", "importe", "coste"])
    return df.sample(frac=1, random_state=semilla).reset_index(drop=True)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("datos/facturas.csv")
    salida.parent.mkdir(parents=True, exist_ok=True)
    f = generar_facturas()
    f.to_csv(salida, index=False)
    print(f"{len(f):,} líneas de factura, {f.cliente.nunique():,} clientes -> {salida}")
