"""Figura del caso: techo de descuento frente a peso en el volumen, con los datos del repo.

Uso: python scripts/figura.py [carpeta_salida]   (por defecto, docs/)
"""
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt

from promociones import segmentar as sg
from promociones import techo as tc
from promociones.abt import construir_abt
from promociones.datos import ANIO, generar_facturas

warnings.filterwarnings("ignore", category=FutureWarning)
DESCUENTO_UNIFORME = 0.12
TINTA, SUAVE, ACENTO, LINEA, FONDO = "#16161a", "#55555f", "#9a3412", "#dededa", "#fbfbf9"


def main(salida: Path) -> None:
    abt = construir_abt(generar_facturas(), ANIO)
    x, _ = sg.preparar(abt)
    segmento = sg.etiquetar(abt, sg.ajustar(x).labels_)
    t = tc.techo_por_segmento(abt, segmento)

    fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor(FONDO)
    ax.set_facecolor(FONDO)
    ax.axhline(DESCUENTO_UNIFORME * 100, color=ACENTO, lw=1.5, ls="--", zorder=1)
    ax.text(99, DESCUENTO_UNIFORME * 100 + 0.6, f"Descuento uniforme: {DESCUENTO_UNIFORME:.0%}",
            color=ACENTO, ha="right", va="bottom", fontsize=12)
    ax.fill_between([0, 100], 0, DESCUENTO_UNIFORME * 100, color=ACENTO, alpha=0.06, zorder=0)
    ax.text(99, 1.0, "por debajo de la línea, la promoción pierde dinero",
            color=ACENTO, ha="right", va="bottom", fontsize=10.5, style="italic")
    for seg, r in t.iterrows():
        xv, yv = r.pct_volumen * 100, r.techo * 100
        ax.scatter(xv, yv, s=260, color=ACENTO if yv < DESCUENTO_UNIFORME * 100 else TINTA,
                   zorder=3)
        ax.annotate(seg, (xv, yv), xytext=(12, 8), textcoords="offset points",
                    fontsize=14, color=TINTA, weight="bold")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, max(t.techo.max() * 100 + 6, 30))
    ax.set_xlabel("% del volumen de la cartera", fontsize=12, color=SUAVE)
    ax.set_ylabel("Techo de descuento (% margen ponderado)", fontsize=12, color=SUAVE)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(LINEA)
    ax.tick_params(colors=SUAVE, labelsize=11)
    ax.set_title("El segmento que más vende es el que menos descuento aguanta",
                 loc="left", fontsize=17, color=TINTA, pad=18, weight="bold")
    fig.text(0.01, 0.01, "Datos sintéticos (github.com/acamposla/promociones-b2b). Reproducen "
             "el orden entre segmentos del caso real, no sus cifras.", fontsize=10, color=SUAVE)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    salida.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "webp"):
        fig.savefig(salida / f"techo-frente-a-volumen.{ext}", facecolor=FONDO)
    print(t[["clientes", "techo", "pct_volumen"]].round(3).to_string())


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs")
