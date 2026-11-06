-- De líneas de factura a una fila por cliente (la ABT del caso).
--
-- Entrada:  facturas(pedido, cliente, fecha, categoria, importe, coste)
-- Parámetro: :anio, el año que se analiza. El anterior solo se usa para la tendencia.
-- Salida:   una fila por cliente con compras en :anio.
--
-- Decisiones:
--   - volumen      = lo facturado en el año (venta neta, sin IVA).
--   - frecuencia   = pedidos distintos, no líneas: una línea por referencia inflaría
--                    la frecuencia de quien compra muchas referencias a la vez.
--   - margen_pct   = margen / volumen. Es la variable de rentabilidad del modelo; el
--                    margen absoluto repite casi lo mismo que el volumen.
--   - tendencia    = volumen del año / volumen del anterior. Un cliente nuevo vale 1
--                    (sin historia no hay tendencia que medir, y 1 es "estable").
--   - Los clientes que dejaron de comprar en :anio no entran: no se les puede ofrecer
--     una promoción sobre una base que no existe.
-- Dialecto: SQLite (viene con Python). Se traslada a PostgreSQL u Oracle cambiando
-- strftime por EXTRACT(YEAR FROM fecha).

WITH lineas AS (
    SELECT
        pedido,
        cliente,
        CAST(strftime('%Y', fecha) AS INTEGER) AS anio,
        categoria,
        importe,
        coste
    FROM facturas
),

anio_actual AS (
    SELECT
        cliente,
        SUM(importe)               AS volumen,
        COUNT(DISTINCT pedido)     AS frecuencia,
        SUM(importe) - SUM(coste)  AS margen,
        COUNT(DISTINCT categoria)  AS n_categorias
    FROM lineas
    WHERE anio = :anio
    GROUP BY cliente
),

anio_anterior AS (
    SELECT cliente, SUM(importe) AS volumen_anterior
    FROM lineas
    WHERE anio = :anio - 1
    GROUP BY cliente
)

SELECT
    a.cliente,
    a.volumen,
    a.frecuencia,
    a.volumen / a.frecuencia                 AS ticket_medio,
    a.margen,
    a.margen / a.volumen                     AS margen_pct,
    a.n_categorias,
    CASE
        WHEN p.volumen_anterior IS NULL OR p.volumen_anterior = 0 THEN 1.0
        ELSE a.volumen / p.volumen_anterior
    END                                      AS tendencia
FROM anio_actual AS a
LEFT JOIN anio_anterior AS p USING (cliente)
WHERE a.volumen > 0
ORDER BY a.cliente;
