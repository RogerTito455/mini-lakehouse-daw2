# Mini Lakehouse – Actividad 3 (Datacycle, Unidad 2)

Pipeline Bronze → Silver → Gold en Python (pandas + SQLite) sobre los datos de `DATA ACTIVITY.zip`.
Es el código del documento de entrega (Anexo A) y reproduce exactamente su salida (Anexo B).

Grupo DAW 2: Roger Tito, Izan Torrico, Zehao Yin. Tutor: Alex Castel.

## Ejecutar

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
# o: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python lakehouse.py   # Bronze -> Silver -> Gold (+ data_lab/lakehouse.db)
.venv/bin/python charts.py      # gráficas en docs/img/
```

Requiere Python 3.11 o superior (el grupo lo ha ejecutado con 3.14).

`lakehouse.py` nunca modifica `data_lab/bronze/`; cada ejecución regenera `silver/`, `gold/`, `lakehouse.db` y `docs/output.txt` (todo lo que imprime se guarda también ahí).

## Estructura

```
data_lab/
├── bronze/   ventas.csv, clientes.json, logs.txt   (tal cual vienen en el zip)
├── silver/   clean_sales.csv, clean_customers.csv, clean_logs.csv,
│             rejected_records.csv (dataset, registro, datos y motivo), quality_report.csv
└── gold/     sales_by_customer.csv, sales_by_product.csv, sales_by_country.csv, total_revenue.csv
docs/
├── output.txt   salida completa de lakehouse.py (Anexo B del documento)
└── img/         gráficas para el documento
```

## Resultados (resumen)

| | Bronze | Silver | Rechazadas |
|---|---|---|---|
| ventas | 200 | 190 | 10 |
| clientes | 250 | 248 | 2 (TestUser, Debug) |
| logs | 205 (+2 líneas en blanco) | 162 | 43 |

- Ingresos totales: **16.355 €** (190 pedidos, 189 clientes). Sin limpiar saldrían 26.624 €.
- Mayor comprador: **Pedro (106)**, 300 €. Ana (101) es quien más pedidos tiene (2, 230 €).
- Producto con más ingresos: **monitor**, 13.190 € (80,6 %). Monitor y teclado empatan en unidades (64).
- Clientes con información incompleta: 112 (sin nombre), 117 (sin país), 138 (país `??`), y 218 con nombre genérico `userN`.

## Decisiones de limpieza

Cada fila rechazada se guarda en `silver/rejected_records.csv` con el primer motivo que incumple.

- **Ventas**: cliente vacío o inexistente (999), cuentas de prueba (200 `TestUser`, 201 `Debug`), producto `test`, importe no numérico (`abc`) o ≤ 0, outlier (> 10× la mediana del producto: 9999), pedidos duplicados (mismo cliente, producto e importe: 31 y 32 repiten el pedido 1).
- **Clientes**: se eliminan las cuentas de prueba (nombre con `test` o `debug`). Los datos incompletos se mantienen y se marcan con `missing_info` y `quality_notes`. `UK` pasa a `GB` (ISO 3166) y `??` o `null` pasan a `Unknown`.
- **Logs**: se eliminan ERROR, DEBUG (`action=test`), líneas sin usuario o sin acción, usuarios no numéricos, cuentas de prueba y usuarios inexistentes. Las líneas WARN (timeouts) se mantienen porque son eventos reales.
