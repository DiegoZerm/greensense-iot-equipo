import pandas as pd

import tablero

INICIO = pd.Timestamp("2026-11-07 17:31", tz=tablero.ZONA)


def test_avance_entre_cero_y_uno():
    assert tablero.avance(INICIO, INICIO - pd.Timedelta(hours=1)) == 0
    assert tablero.avance(INICIO, INICIO + pd.Timedelta(hours=36)) == 0.5
    assert tablero.avance(INICIO, INICIO + pd.Timedelta(hours=100)) == 1


def test_solo_cuentan_los_minutos_completos():
    assert tablero.esperadas_hasta(INICIO, INICIO + pd.Timedelta(seconds=59)) == 0
    assert tablero.esperadas_hasta(INICIO, INICIO + pd.Timedelta(minutes=6, seconds=44)) == 6
    assert tablero.esperadas_hasta(INICIO, INICIO + pd.Timedelta(hours=72)) == 4320
    assert tablero.esperadas_hasta(INICIO, INICIO - pd.Timedelta(hours=1)) == 0


def test_a_tabla_ordena_en_hora_local_y_quita_repetidas():
    lecturas = [
        {"ts": "2026-11-07T23:33:49Z", "arranque": 14, "seq": 2, "temperatura": 22.0,
         "humedad_aire": 70.0, "humedad_sustrato": 54.0, "muestras": 5, "rssi": -55},
        {"ts": "2026-11-07T23:31:49Z", "arranque": 14, "seq": 0, "temperatura": 22.8,
         "humedad_aire": 69.9, "humedad_sustrato": 52.7, "muestras": 5, "rssi": -55},
        {"ts": "2026-11-07T23:31:49Z", "arranque": 14, "seq": 0, "temperatura": 22.8,
         "humedad_aire": 69.9, "humedad_sustrato": 52.7, "muestras": 5, "rssi": -55},
    ]
    datos = tablero.a_tabla(lecturas)
    assert len(datos) == 2
    assert datos.index[0] == pd.Timestamp("2026-11-07 17:31:49", tz=tablero.ZONA)
    assert tablero.a_tabla([]).empty


def test_riegos_se_anotan_y_se_leen_en_orden(tmp_path):
    ruta = tmp_path / "riegos.csv"
    assert tablero.leer_riegos(ruta).empty
    tablero.anotar_riego(pd.Timestamp("2026-11-08 09:00", tz=tablero.ZONA), ruta)
    tablero.anotar_riego(pd.Timestamp("2026-11-07 18:00", tz=tablero.ZONA), ruta)

    riegos = tablero.leer_riegos(ruta)
    assert [r.hour for r in riegos] == [18, 9]
    assert ruta.read_text().startswith("fecha_hora\n")
