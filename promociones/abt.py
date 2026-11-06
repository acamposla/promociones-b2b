"""Construcción de la ABT (una fila por cliente) a partir de las líneas de factura."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

SQL_ABT = Path(__file__).resolve().parent.parent / "sql" / "abt_clientes.sql"
VARIABLES = ["volumen", "frecuencia", "ticket_medio", "margen_pct", "n_categorias", "tendencia"]


def construir_abt(facturas: pd.DataFrame, anio: int) -> pd.DataFrame:
    """Ejecuta sql/abt_clientes.sql sobre las facturas en una base SQLite en memoria."""
    with sqlite3.connect(":memory:") as con:
        facturas.to_sql("facturas", con, index=False)
        return pd.read_sql_query(SQL_ABT.read_text(encoding="utf-8"), con, params={"anio": anio})


def construir_abt_pandas(facturas: pd.DataFrame, anio: int) -> pd.DataFrame:
    """La misma ABT en pandas. Solo sirve para comprobar el SQL en los tests."""
    f = facturas.assign(anio=pd.to_datetime(facturas.fecha).dt.year)
    act = f[f.anio == anio].groupby("cliente").agg(
        volumen=("importe", "sum"), frecuencia=("pedido", "nunique"),
        coste=("coste", "sum"), n_categorias=("categoria", "nunique"))
    ant = f[f.anio == anio - 1].groupby("cliente").importe.sum().rename("volumen_anterior")
    abt = act.join(ant, how="left")
    abt["ticket_medio"] = abt.volumen / abt.frecuencia
    abt["margen"] = abt.volumen - abt.coste
    abt["margen_pct"] = abt.margen / abt.volumen
    abt["tendencia"] = (abt.volumen / abt.volumen_anterior).where(abt.volumen_anterior > 0, 1.0)
    abt = abt[abt.volumen > 0].reset_index()
    return abt[["cliente", "volumen", "frecuencia", "ticket_medio", "margen", "margen_pct",
                "n_categorias", "tendencia"]].sort_values("cliente").reset_index(drop=True)
