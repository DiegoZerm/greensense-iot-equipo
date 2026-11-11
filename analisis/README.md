# Análisis de datos

Dos notebooks con pandas y scikit-learn, y un programa que mide los indicadores de éxito de la propuesta.

| Archivo | Qué hace |
|---|---|
| `notebooks/01_descriptivo.ipynb` | Calidad de los datos, estadísticas, ciclo diario, tiempo dentro del rango del cultivo y correlaciones |
| `notebooks/02_regresion.ipynb` | Regresión lineal múltiple para estimar la humedad del sustrato dentro de una hora, comparada contra suponer que el valor sigue igual |
| `medir_indicadores.py` | Mide contra un servidor en marcha la duración, las lecturas perdidas, si se puede reconstruir cada día y el tiempo del sensor al panel |
| `tablero.py` | Tablero en vivo de la prueba de campo, con registro de riegos |
| `comun.py` | Las funciones de los notebooks, con sus pruebas en `tests/` |

## Tablero de la prueba de campo

`tablero.py` muestra, mientras corre la prueba:
- el avance de la prueba;
- las lecturas recibidas contra las esperadas y el porcentaje de pérdidas;
- la última lectura y los valores actuales;
- las gráficas desde el inicio y los huecos;
- las alertas del nodo.

También sirve para anotar cada riego, que queda en `datos/riegos.csv` para el análisis. Se actualiza solo cada minuto.

```bash
cd analisis
.venv/bin/pip install -r requirements.txt     # solo la primera vez
.venv/bin/streamlit run tablero.py            # http://localhost:8502
```

En la barra lateral van el correo y la contraseña de la app, el nodo y la hora de inicio de la prueba. Solo se abre en esta computadora (`.streamlit/config.toml`). Si el servidor corre en Docker, el tablero lo encuentra solo en el puerto 8080.

## Correr los notebooks

1. En la app, entra a **Historial**, elige el nodo, la vista **Rango** y las fechas de la prueba, y presiona **Lecturas CSV**. Necesita un rol que pueda exportar: supervisor o administrador.
2. Guarda el archivo en `analisis/datos/`. Esa carpeta no se sube al repositorio.
3. Corre:

   ```bash
   cd analisis
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/jupyter lab notebooks
   ```

Se usa el CSV más reciente de la carpeta; para elegir otro, define `GS_CSV=/ruta/al/archivo.csv`. Los datos de la prueba de campo de 72 horas están en [`prueba-72h/`](prueba-72h/README.md), con la forma de reproducir los resultados. En Jupyter, usa **Run > Run All Cells**. Los notebooks se suben sin resultados: se generan al correrlos con los datos de la prueba.

**Los datos de `gs-demo` sirven para probar que todo corre, pero no son evidencia.** Los resultados que se entreguen deben salir del nodo real. Los notebooks muestran el archivo que usaron y avisan si el periodo es menor a 7 días.

Si el sustrato no tiene datos o casi no varía, por ejemplo porque el sensor no está enterrado, la regresión estima la temperatura y lo avisa. Es el plan B de la propuesta.

## Medir los indicadores

```bash
cd analisis
python3 medir_indicadores.py --url http://localhost:8000 --correo <correo> --nodo maceta1 \
    --desde 2026-11-07 --hasta 2026-11-10 --lecturas 10
```

No necesita el entorno de los notebooks. Pide la contraseña sin mostrarla. El nodo debe estar enviando, porque espera `--lecturas` lecturas nuevas para medir el tiempo del sensor al panel; con `--lecturas 0` se omite. Ese tiempo compara la hora que pone el nodo (sincronizada por NTP) con el reloj de la computadora donde corre el programa, así que incluye la diferencia que haya entre los dos.

### El indicador que se mide a mano: push en menos de 1 minuto

El programa no puede ver el teléfono. La propuesta pide que, al simular una condición fuera de rango, la notificación llegue en menos de un minuto:

1. Activa las notificaciones en el teléfono ([infra/README.md](../infra/README.md)).
2. Provoca una alerta crítica. Una alerta de temperatura necesita 5 minutos fuera de rango antes de volverse crítica; ese tiempo es del propio cultivo y no cuenta como retraso.
3. En la app, en **Alertas**, anota la hora en que la alerta pasó a crítica y compárala con la hora de la notificación en el teléfono.
