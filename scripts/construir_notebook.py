"""Escribe notebooks/caso.ipynb y lo ejecuta de principio a fin sobre los datos sintéticos.

Uso: python scripts/construir_notebook.py
"""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "notebooks" / "caso.ipynb"

celdas = []


def md(texto):
    celdas.append(nbf.v4.new_markdown_cell(texto.strip()))


def code(texto):
    celdas.append(nbf.v4.new_code_cell(texto.strip()))


md("""
# El grupo que más compra es el que menos descuento aguanta

Un distribuidor B2B da la misma promoción a todos sus clientes. La pregunta es a quién se le
puede descontar, cuánto y a cambio de qué. Este notebook reproduce el método de principio a
fin: de las líneas de factura a una fila por cliente, de ahí a cuatro grupos, un techo de
descuento por grupo y la rentabilidad de un rappel por crecimiento.

**Los datos son sintéticos.** Salen de `promociones/datos.py` con una semilla fija e imitan la
forma de una cartera real (cola larga de volumen, margen independiente del tamaño, un grupo
pequeño que crece deprisa), no sus cifras. El caso contado está en
[alejandrocamposlamas.com](https://alejandrocamposlamas.com/portfolio/el-grupo-que-mas-compra/).
""")

code("""
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.cluster import KMeans

from promociones import segmentar as sg
from promociones import techo as tc
from promociones.abt import construir_abt
from promociones.datos import ANIO, generar_facturas

pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
TINTA, SUAVE, ACENTO, LINEA, FONDO = "#16161a", "#55555f", "#9a3412", "#dededa", "#fbfbf9"
plt.rcParams.update({"figure.facecolor": FONDO, "axes.facecolor": FONDO,
                     "axes.edgecolor": LINEA, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 11})
""")

md("""
## 1. De la factura al cliente

La facturación llega como líneas: pedido, cliente, fecha, categoría, importe y coste. El
análisis necesita una fila por cliente con seis variables. La consulta está en
`sql/abt_clientes.sql` y corre sobre SQLite, la base que viene con Python.
""")

code("""
facturas = generar_facturas()
abt = construir_abt(facturas, ANIO)
print(f"{len(facturas):,} líneas de factura -> {len(abt):,} clientes con compras en {ANIO}")
facturas.head()
""")

code("""
abt.head()
""")

code("""
abt[["volumen", "frecuencia", "ticket_medio", "margen_pct", "n_categorias", "tendencia"]].describe()
""")

md("""
El volumen tiene una cola muy larga: la media se va por encima del tercer cuartil. Por eso
las variables de escala entran al modelo en logaritmo y con un escalado por mediana y rango
intercuartílico, que no se deja arrastrar por los pocos clientes enormes. El margen entra como
porcentaje sobre venta: el margen en euros repite casi lo mismo que el volumen.
""")

md("""
## 2. Cuántos grupos

Se prueba de 2 a 10 grupos y se mira lo que dicen las medidas habituales.
""")

code("""
x, escalador = sg.preparar(abt)
barrido = sg.barrido_k(x)
barrido
""")

code("""
fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4))
a1.plot(barrido.index, barrido.silueta, marker="o", color=TINTA)
a1.set_title("Silueta (más es mejor)", loc="left")
a2.plot(barrido.index, barrido.calinski_harabasz, marker="o", color=TINTA)
a2.set_title("Calinski-Harabász (más es mejor)", loc="left")
for a in (a1, a2):
    a.axvline(4, color=ACENTO, ls="--", lw=1)
    a.set_xlabel("número de grupos")
plt.tight_layout()
""")

code("""
print("La silueta prefiere k =", barrido.silueta.idxmax())
print("Calinski-Harabász prefiere k =", barrido.calinski_harabasz.idxmax())
""")

md("""
Las medidas no coinciden entre sí, y ninguna responde a la pregunta de negocio: si con menos
grupos ventas puede hacer ofertas distintas a quien las necesita distintas. Se mira dónde cae el
volumen de cada uno de los cuatro grupos finales cuando se fuerza a dos o a tres.
""")

code("""
km = sg.ajustar(x, k=4)
segmento = sg.etiquetar(abt, km.labels_)

for k in (2, 3):
    grupos = KMeans(k, random_state=sg.SEMILLA, n_init=10).fit_predict(x)
    reparto = pd.crosstab(segmento, grupos, values=abt.volumen, aggfunc="sum", normalize="index")
    print(f"k={k}: parte del volumen de cada segmento que cae en cada grupo")
    print(reparto.reindex(tc.ORDEN).round(2), end="\\n\\n")
""")

md("""
En estos datos, con dos o con tres grupos, Premium y Commodity caen juntos. Son los dos grupos
grandes, y necesitan ofertas opuestas: a uno hay que cuidarle el precio y al otro pedirle volumen
a cambio. Por eso el caso se queda con cuatro aunque no sea el número que eligen las dos medidas.
En el caso real el patrón era parecido pero menos limpio: con tres grupos, una parte de los
clientes de margen estrecho se iba con la masa de clientes pequeños.
""")

md("""
## 3. Los cuatro grupos
""")

code("""
sg.perfil(abt, segmento)
""")

code("""
colores = {"Premium": TINTA, "Commodity": ACENTO, "Emergentes": "#2f6f73", "Masa": "#9c9ca3"}
fig, ax = plt.subplots(figsize=(10, 6))
for seg, color in colores.items():
    m = segmento == seg
    ax.scatter(abt.volumen[m], abt.margen_pct[m] * 100, s=14, alpha=0.6, color=color, label=seg)
ax.set_xscale("log")
ax.set_xlabel("volumen anual por cliente (€, escala logarítmica)")
ax.set_ylabel("margen sobre venta (%)")
ax.set_title("Entre los clientes grandes, el margen separa dos negocios distintos", loc="left")
ax.legend(frameon=False)
plt.tight_layout()
""")

md("""
## 4. Reglas que ventas puede decir por teléfono

Un K-Means no se explica en una llamada. Un árbol de decisión de tres niveles traduce los
grupos a cortes en unidades de negocio (euros, pedidos, porcentaje de margen). El acierto mide
cuántos clientes clasifican bien las reglas frente a los grupos del K-Means. Es descriptivo: el
árbol aprende de las mismas variables que formaron los grupos, así que no valida el clustering.
""")

code("""
arbol, acierto, texto = sg.reglas(abt, segmento)
print(f"Las reglas aciertan el grupo del {acierto:.0%} de los clientes\\n")
print(texto)
""")

md("""
## 5. El techo de descuento de cada grupo

El techo es el margen del grupo pesado por volumen. Una promoción de precio por encima de ese
porcentaje pierde dinero en el grupo, la acepte quien la acepte. El suelo (percentil 25 del
margen) marca un descuento con el que al menos tres de cada cuatro clientes siguen ganando.
""")

code("""
techos = tc.techo_por_segmento(abt, segmento)
techos
""")

code("""
DESCUENTO_UNIFORME = 0.12
fig, ax = plt.subplots(figsize=(10, 5.5))
ax.axhline(DESCUENTO_UNIFORME * 100, color=ACENTO, ls="--", lw=1.5)
ax.fill_between([0, 100], 0, DESCUENTO_UNIFORME * 100, color=ACENTO, alpha=0.06)
ax.text(99, DESCUENTO_UNIFORME * 100 + 0.6, f"descuento igual para todos: {DESCUENTO_UNIFORME:.0%}",
        color=ACENTO, ha="right")
for seg, fila in techos.iterrows():
    xv, yv = fila.pct_volumen * 100, fila.techo * 100
    ax.scatter(xv, yv, s=220, color=ACENTO if yv < DESCUENTO_UNIFORME * 100 else TINTA, zorder=3)
    ax.annotate(seg, (xv, yv), xytext=(10, 8), textcoords="offset points", weight="bold")
ax.set_xlim(0, 100)
ax.set_ylim(0, techos.techo.max() * 100 + 6)
ax.set_xlabel("% del volumen de la cartera")
ax.set_ylabel("techo de descuento (% de margen ponderado)")
ax.set_title("El grupo que más vende es el que menos descuento aguanta", loc="left")
plt.tight_layout()
""")

code("""
print("Parte de los clientes de cada grupo con margen propio por debajo del descuento uniforme:")
tc.bajo_el_agua(abt, segmento, DESCUENTO_UNIFORME).round(2)
""")

md("""
## 6. Qué hacer con cada grupo

La rejilla cruza cada grupo con su cuartil de volumen y aplica dos umbrales que decide negocio,
no el modelo: el techo mínimo para que una oferta de precio tenga hueco y el volumen mínimo para
que compense gestionarla.
""")

code("""
tc.rejilla(abt, segmento, desc_min=0.06, vol_min=2_000)
""")

md("""
## 7. El rappel por crecimiento

En vez de descontar sobre todo lo que compra el cliente, se descuenta solo sobre lo que crece:
"si me compras un 6 % más de lo que ya me compras, te descuento un d % sobre lo que crezcas". La
matriz da el neto para el grupo con distintos descuentos y tasas de aceptación. El signo lo
decide el descuento frente al techo; la aceptación solo cambia el tamaño.
""")

code("""
for grupo in ("Premium", "Commodity"):
    print(f"{grupo}: techo {techos.loc[grupo, 'techo']:.1%}. Neto del rappel en € (u = 6 %)")
    print(tc.escenarios(abt, segmento, grupo).round(0), end="\\n\\n")
""")

md("""
## 8. Lo que estos datos no pueden decir

La factura dice quién compró y con qué descuento. No dice a quién se le ofreció la promoción y
no compró, ni si el descuento venía de un rappel o de un precio rebajado. Con eso se calcula el
techo, que no depende de la aceptación, pero no el efecto real de una campaña. Para medirlo
hace falta un piloto: apuntar antes de lanzar a quién se le ofrece y dejar fuera, al azar, una
parte de cada grupo como control.
""")

nb = nbf.v4.new_notebook()
nb.cells = celdas
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
NotebookClient(nb, timeout=300, kernel_name="python3",
               resources={"metadata": {"path": str(RAIZ)}}).execute()
SALIDA.parent.mkdir(exist_ok=True)
nbf.write(nb, SALIDA)
print(f"Escrito y ejecutado: {SALIDA}")
