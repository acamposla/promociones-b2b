"""Comprobaciones del caso: datos reproducibles, SQL correcto y el hallazgo se sostiene."""
import warnings

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import KMeans

from promociones import segmentar as sg
from promociones import techo as tc
from promociones.abt import VARIABLES, construir_abt, construir_abt_pandas
from promociones.datos import ANIO, generar_facturas

warnings.filterwarnings("ignore", category=FutureWarning)


@pytest.fixture(scope="module")
def facturas():
    return generar_facturas()


@pytest.fixture(scope="module")
def abt(facturas):
    return construir_abt(facturas, ANIO)


@pytest.fixture(scope="module")
def modelo(abt):
    x, _ = sg.preparar(abt)
    km = sg.ajustar(x)
    return x, km, sg.etiquetar(abt, km.labels_)


# --- Datos -------------------------------------------------------------------------

def test_generador_reproducible(facturas):
    otra = generar_facturas()
    pd.testing.assert_frame_equal(facturas, otra)


def test_facturas_sin_importes_negativos(facturas):
    assert (facturas.importe > 0).all()
    assert facturas.fecha.str[:4].isin([str(ANIO - 1), str(ANIO)]).all()


# --- ABT ---------------------------------------------------------------------------

def test_sql_igual_que_pandas(facturas, abt):
    ref = construir_abt_pandas(facturas, ANIO)
    assert list(abt.cliente) == list(ref.cliente)
    np.testing.assert_allclose(abt[VARIABLES].to_numpy(), ref[VARIABLES].to_numpy(), rtol=1e-9)


def test_abt_una_fila_por_cliente(abt):
    assert abt.cliente.is_unique
    assert abt[VARIABLES].notna().all().all()


def test_ticket_por_frecuencia_es_volumen(abt):
    np.testing.assert_allclose(abt.ticket_medio * abt.frecuencia, abt.volumen)


def test_base_anterior_negativa_por_abonos():
    """Un abono que deja negativo el año anterior no puede dar una tendencia negativa."""
    f = pd.DataFrame({
        "pedido": ["A1", "A2", "B1", "B2"],
        "cliente": ["A", "A", "B", "B"],
        "fecha": [f"{ANIO - 1}-03-01", f"{ANIO}-03-01", f"{ANIO - 1}-03-01", f"{ANIO}-03-01"],
        "categoria": ["cat_01"] * 4,
        "importe": [-500.0, 1_000.0, 800.0, 1_000.0],
        "coste": [-400.0, 800.0, 600.0, 800.0],
    })
    sql, ref = construir_abt(f, ANIO), construir_abt_pandas(f, ANIO)
    np.testing.assert_allclose(sql.tendencia, ref.tendencia)
    assert sql.set_index("cliente").tendencia.to_dict() == {"A": 1.0, "B": 1.25}


def test_cliente_nuevo_tiene_tendencia_uno(facturas, abt):
    con_historia = set(facturas[facturas.fecha.str.startswith(str(ANIO - 1))].cliente)
    nuevos = abt[~abt.cliente.isin(con_historia)]
    assert len(nuevos) > 0
    assert (nuevos.tendencia == 1.0).all()


# --- Rappel ------------------------------------------------------------------------

@pytest.mark.parametrize("r", [0.05, 0.2, 0.9])
def test_neto_cero_cuando_descuento_igual_a_margen(r):
    assert tc.neto_rappel(1_000_000, 0.18, d=0.18, u=0.05, r=r) == pytest.approx(0.0)


def test_neto_cambia_de_signo_en_el_techo():
    assert tc.neto_rappel(1_000_000, 0.18, d=0.10, u=0.05, r=0.2) > 0
    assert tc.neto_rappel(1_000_000, 0.18, d=0.25, u=0.05, r=0.2) < 0


# --- Hallazgo ----------------------------------------------------------------------

def test_cuatro_segmentos_con_nombre(modelo):
    _, _, seg = modelo
    assert set(seg) == {"Premium", "Commodity", "Emergentes", "Masa"}


def test_el_grupo_que_mas_vende_aguanta_menos(abt, modelo):
    _, _, seg = modelo
    t = tc.techo_por_segmento(abt, seg)
    assert t.pct_volumen.idxmax() == "Commodity"
    assert t.techo.idxmin() == "Commodity"
    assert t.techo.idxmax() == "Premium"


def test_por_cliente_el_grande_es_premium(abt, modelo):
    _, _, seg = modelo
    medias = abt.groupby(seg).volumen.median()
    assert medias.idxmax() == "Premium"


def test_con_menos_grupos_premium_y_commodity_van_juntos(abt, modelo):
    x, _, seg = modelo
    for k in (2, 3):
        grupos = KMeans(k, random_state=sg.SEMILLA, n_init=10).fit_predict(x)
        vol = pd.crosstab(seg, grupos, values=abt.volumen, aggfunc="sum", normalize="index")
        assert vol.loc["Premium"].idxmax() == vol.loc["Commodity"].idxmax(), f"k={k}"


def test_las_reglas_aciertan_la_mayoria(abt, modelo):
    _, _, seg = modelo
    _, acierto, texto = sg.reglas(abt, seg)
    assert acierto > 0.8
    assert "margen_pct" in texto
