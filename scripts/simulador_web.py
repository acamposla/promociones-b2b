"""Exporta un simulador del rappel, autónomo (HTML + JS sin dependencias), con los datos del repo.

Reproduce lo que hacía el simulador de Power BI del caso: eliges grupo y cuartil de volumen,
mueves crecimiento exigido, descuento y aceptación, y ves el neto, el techo, la holgura y qué
parte de los clientes queda con un margen por debajo del descuento.

Uso: python scripts/simulador_web.py <salida.html>
"""
import json
import sys
import warnings
from pathlib import Path

import pandas as pd

from promociones import segmentar as sg
from promociones import techo as tc
from promociones.abt import construir_abt
from promociones.datos import ANIO, generar_facturas

warnings.filterwarnings("ignore", category=FutureWarning)


def datos() -> dict:
    abt = construir_abt(generar_facturas(), ANIO)
    x, _ = sg.preparar(abt)
    abt["segmento"] = sg.etiquetar(abt, sg.ajustar(x).labels_)
    abt["cuartil"] = abt.groupby("segmento").volumen.transform(
        lambda v: pd.qcut(v.rank(method="first"), 4, labels=False) + 1)
    seg_idx = {s: i for i, s in enumerate(tc.ORDEN)}
    filas = [[seg_idx[s], int(q), round(float(v)), round(float(m), 4)]
             for s, q, v, m in abt[["segmento", "cuartil", "volumen", "margen_pct"]].itertuples(
                 index=False)]
    return {"segmentos": tc.ORDEN, "clientes": filas}


PLANTILLA = r"""<!-- Generado por promociones-b2b/scripts/simulador_web.py. No editar a mano. -->
<figure class="simulador" id="simulador-rappel">
<style>
#simulador-rappel{--s-tinta:var(--tinta,#16161a);--s-suave:var(--tinta-suave,#55555f);
--s-fondo:var(--fondo-sutil,#f1f1ec);--s-linea:var(--linea,#dededa);--s-acento:var(--acento,#9a3412);
--s-ok:#2f6f73;font-family:var(--sans,system-ui,sans-serif);line-height:1.35;margin:2rem 0;padding:1.25rem;
background:var(--s-fondo);border:1px solid var(--s-linea);border-radius:10px;color:var(--s-tinta)}
#simulador-rappel .fila{display:flex;flex-wrap:wrap;gap:.75rem 1.5rem;margin-bottom:1rem}
#simulador-rappel label{font-size:.85rem;color:var(--s-suave);display:flex;flex-direction:column;gap:.3rem;flex:1 1 9rem}
#simulador-rappel select{font:inherit;font-size:.95rem;padding:.35rem .4rem;border:1px solid var(--s-linea);
border-radius:6px;background:transparent;color:var(--s-tinta)}
#simulador-rappel input[type=range]{width:100%;accent-color:var(--s-acento)}
#simulador-rappel .valor{font-variant-numeric:tabular-nums;color:var(--s-tinta);font-weight:600}
#simulador-rappel .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr));gap:.75rem;margin-top:.5rem}
#simulador-rappel .kpi{border-top:2px solid var(--s-linea);padding-top:.5rem}
#simulador-rappel .kpi b{display:block;font-size:1.35rem;font-variant-numeric:tabular-nums}
#simulador-rappel .kpi span{font-size:.8rem;color:var(--s-suave)}
#simulador-rappel .estado.pierde b{color:var(--s-acento)}
#simulador-rappel .estado.gana b{color:var(--s-ok)}
#simulador-rappel .barra{position:relative;height:10px;background:var(--s-linea);border-radius:5px;margin:1.1rem 0 .3rem}
#simulador-rappel .barra i{position:absolute;top:-4px;width:2px;height:18px;background:var(--s-tinta)}
#simulador-rappel .barra i.d{background:var(--s-acento)}
#simulador-rappel .leyenda{font-size:.8rem;color:var(--s-suave)}
#simulador-rappel figcaption{font-size:.8rem;color:var(--s-suave);margin-top:1rem}
</style>
<div class="fila">
  <label>Grupo<select data-k="seg"><option value="-1">Todos</option></select></label>
  <label>Cuartil de volumen<select data-k="cua"><option value="0">Todos</option>
    <option value="1">Q1, los más pequeños</option><option value="2">Q2</option>
    <option value="3">Q3</option><option value="4">Q4, los más grandes</option></select></label>
</div>
<div class="fila">
  <label>Crecimiento exigido <span class="valor" data-v="u"></span>
    <input type="range" data-k="u" min="1" max="20" step="1" value="6"></label>
  <label>Descuento sobre lo que crece <span class="valor" data-v="d"></span>
    <input type="range" data-k="d" min="1" max="40" step="1" value="8"></label>
  <label>Clientes que aceptan y cumplen <span class="valor" data-v="r"></span>
    <input type="range" data-k="r" min="5" max="100" step="5" value="25"></label>
</div>
<div class="kpis">
  <div class="kpi estado"><b data-o="neto"></b><span>neto de la promoción</span></div>
  <div class="kpi"><b data-o="techo"></b><span>techo de descuento</span></div>
  <div class="kpi"><b data-o="holgura"></b><span>holgura frente al techo</span></div>
  <div class="kpi"><b data-o="agua"></b><span>clientes con margen por debajo del descuento</span></div>
  <div class="kpi"><b data-o="n"></b><span>clientes en la selección</span></div>
</div>
<div class="barra" aria-hidden="true"><i class="t"></i><i class="d"></i></div>
<p class="leyenda">Línea negra: techo del grupo. Línea de color: descuento elegido. Escala de 0 a 50 %.</p>
<figcaption>Datos sintéticos del repositorio
<a href="https://github.com/acamposla/promociones-b2b">promociones-b2b</a>. Neto = aceptación ×
crecimiento × volumen × (techo − descuento).</figcaption>
</figure>
<script>
(function () {
  var fig = document.getElementById('simulador-rappel');
  if (!fig) return;
  var D = __DATOS__;
  var sel = fig.querySelector('[data-k=seg]');
  D.segmentos.forEach(function (s, i) {
    var o = document.createElement('option'); o.value = i; o.textContent = s; sel.appendChild(o);
  });
  sel.value = '1';
  var eur = new Intl.NumberFormat('es-ES', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0});
  var pct = new Intl.NumberFormat('es-ES', {style: 'percent', maximumFractionDigits: 1});
  function q(k) { return fig.querySelector('[data-k=' + k + ']'); }
  function out(k, t) { fig.querySelector('[data-o=' + k + ']').textContent = t; }
  function calc() {
    var s = +q('seg').value, c = +q('cua').value;
    var u = q('u').value / 100, d = q('d').value / 100, r = q('r').value / 100;
    ['u', 'd', 'r'].forEach(function (k) {
      fig.querySelector('[data-v=' + k + ']').textContent = q(k).value + ' %';
    });
    var V = 0, M = 0, n = 0, agua = 0;
    D.clientes.forEach(function (f) {
      if ((s < 0 || f[0] === s) && (c === 0 || f[1] === c)) {
        V += f[2]; M += f[2] * f[3]; n += 1; if (f[3] < d) agua += 1;
      }
    });
    var m = V ? M / V : 0, neto = r * u * V * (m - d);
    out('neto', eur.format(neto)); out('techo', pct.format(m));
    var pp = ((m - d) * 100).toLocaleString('es-ES', {maximumFractionDigits: 1});
    out('holgura', (m - d >= 0 ? '+' : '') + pp + ' pp');
    out('agua', n ? pct.format(agua / n) : '-'); out('n', n.toLocaleString('es-ES'));
    var est = fig.querySelector('.estado');
    est.classList.toggle('pierde', neto < 0); est.classList.toggle('gana', neto >= 0);
    fig.querySelector('.barra .t').style.left = Math.min(m / 0.5, 1) * 100 + '%';
    fig.querySelector('.barra .d').style.left = Math.min(d / 0.5, 1) * 100 + '%';
  }
  fig.querySelectorAll('select, input').forEach(function (e) { e.addEventListener('input', calc); });
  calc();
})();
</script>
"""


if __name__ == "__main__":
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/simulador.html")
    salida.parent.mkdir(parents=True, exist_ok=True)
    html = PLANTILLA.replace("__DATOS__", json.dumps(datos(), separators=(",", ":")))
    salida.write_text(html, encoding="utf-8")
    print(f"{salida} ({len(html) / 1024:.0f} KB)")
