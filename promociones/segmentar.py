"""Segmentación de la cartera: K-Means sobre seis variables y reglas legibles con un árbol."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, silhouette_score
from sklearn.preprocessing import RobustScaler
from sklearn.tree import DecisionTreeClassifier, export_text

from promociones.abt import VARIABLES

# Magnitudes de cola larga: log1p. margen_pct es una tasa acotada y n_categorias un
# conteo pequeño, así que van sin log.
CON_LOG = ["volumen", "frecuencia", "ticket_medio", "tendencia"]
SEMILLA = 42


def preparar(abt: pd.DataFrame) -> tuple[np.ndarray, RobustScaler]:
    """log1p en las variables de cola larga y escalado robusto (mediana e IQR).

    RobustScaler y no StandardScaler: con cola larga, la media y la desviación las
    marcan los pocos clientes enormes, y el resto queda aplastado cerca de cero.
    """
    x = abt[VARIABLES].copy()
    x[CON_LOG] = np.log1p(x[CON_LOG])
    escalador = RobustScaler()
    return escalador.fit_transform(x), escalador


def barrido_k(x: np.ndarray, ks=(2, 3, 4, 5, 6, 7, 8, 9, 10)) -> pd.DataFrame:
    """Inercia, silueta, Calinski-Harabász y tamaño del grupo más pequeño para cada k."""
    filas = []
    for k in ks:
        km = KMeans(n_clusters=k, random_state=SEMILLA, n_init=10).fit(x)
        filas.append({
            "k": k,
            "inercia": km.inertia_,
            "silueta": silhouette_score(x, km.labels_),
            "calinski_harabasz": calinski_harabasz_score(x, km.labels_),
            "grupo_menor": int(np.bincount(km.labels_).min()),
        })
    return pd.DataFrame(filas).set_index("k")


def ajustar(x: np.ndarray, k: int = 4) -> KMeans:
    return KMeans(n_clusters=k, random_state=SEMILLA, n_init=20).fit(x)


def etiquetar(abt: pd.DataFrame, grupos: np.ndarray) -> pd.Series:
    """Pone nombre a cada grupo por su perfil, sin depender del número que le da K-Means.

    Emergentes = mayor tendencia; Premium = mayor margen del resto; Masa = menor
    volumen de los que quedan; Commodity = el último (grande y de margen estrecho).
    Solo tiene sentido con k=4.
    """
    m = abt.assign(grupo=grupos).groupby("grupo").agg(
        vol=("volumen", "mean"), mpct=("margen_pct", "mean"), tend=("tendencia", "mean"))
    emergentes = m.tend.idxmax()
    premium = m.drop(emergentes).mpct.idxmax()
    masa = m.drop([emergentes, premium]).vol.idxmin()
    commodity = next(g for g in m.index if g not in (emergentes, premium, masa))
    nombres = {premium: "Premium", commodity: "Commodity", emergentes: "Emergentes", masa: "Masa"}
    return pd.Series(grupos, index=abt.index).map(nombres).rename("segmento")


def reglas(abt: pd.DataFrame, segmento: pd.Series, profundidad: int = 3):
    """Árbol de decisión sobre las variables en unidades originales (€, pedidos, %).

    Es descriptivo, no una validación: aprende de las mismas variables que formaron
    los grupos. Lo que aporta son cortes que un comercial puede decir en una frase.
    Devuelve (árbol, acierto sobre las etiquetas, texto de las reglas).
    """
    arbol = DecisionTreeClassifier(max_depth=profundidad, random_state=SEMILLA)
    arbol.fit(abt[VARIABLES], segmento)
    acierto = arbol.score(abt[VARIABLES], segmento)
    return arbol, acierto, export_text(arbol, feature_names=VARIABLES)


def perfil(abt: pd.DataFrame, segmento: pd.Series) -> pd.DataFrame:
    """Perfil por segmento: clientes, peso en volumen, medianas y margen ponderado."""
    d = abt.assign(segmento=segmento)
    g = d.groupby("segmento")
    out = pd.DataFrame({
        "clientes": g.size(),
        "pct_clientes": g.size() / len(d),
        "pct_volumen": g.volumen.sum() / d.volumen.sum(),
        "volumen_medio": g.volumen.mean(),
        "volumen_mediano": g.volumen.median(),
        "margen_pct_mediano": g.margen_pct.median(),
        "frecuencia_mediana": g.frecuencia.median(),
        "tendencia_mediana": g.tendencia.median(),
    })
    return out.sort_values("pct_volumen", ascending=False)
