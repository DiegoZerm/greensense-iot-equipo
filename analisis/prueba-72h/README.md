# Datos de la prueba de campo de 72 horas

Lecturas del nodo `maceta1` del 7 de noviembre de 2026 a las 17:31 al 10 de noviembre a las 17:31, una por minuto. Son los datos con los que se obtuvieron los resultados del reporte.

| Archivo | Contenido |
|---|---|
| `lecturas_maceta1_2026-11-07_2026-11-10.csv` | Exportación de la app (**Historial > Lecturas CSV**), sin cambios: 4 052 lecturas |
| `lecturas_maceta1_depurado.csv` | Las mismas 4 052 lecturas, con la humedad del sustrato vacía entre las 17:59 y las 19:23 del 7 de noviembre |
| `riegos.csv` | Riegos anotados en el tablero durante la prueba |

## Qué se depuró

Solo la humedad del sustrato de 84 lecturas, de las cuales 64 ya venían vacías. En ese intervalo se compactó la tierra alrededor del sensor, se regó la maceta y se corrigió la calibración, así que el valor no representa al sustrato. La temperatura y la humedad del aire de esas lecturas se conservan. No se quitó ninguna fila.

## Qué falta

Se esperaban 4 320 lecturas y hay 4 052. Las 268 que faltan son un solo hueco, del 7 de noviembre a las 21:05 al 8 de noviembre a las 01:34, mientras estuvo suspendida la computadora del servidor. Los archivos lo muestran tal cual: no se rellenó.

## Columnas

`fecha_hora` (hora del centro de México), `nodo`, `arranque` (número de arranque del nodo), `seq` (consecutivo dentro del arranque), `temperatura` (°C), `humedad_aire` (%), `humedad_sustrato` (%), `muestras` (mediciones promediadas en la lectura) y `rssi` (señal WiFi, dBm).

## Reproducir el análisis

```bash
cd analisis
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
GS_CSV=$PWD/prueba-72h/lecturas_maceta1_depurado.csv .venv/bin/jupyter lab notebooks
```
