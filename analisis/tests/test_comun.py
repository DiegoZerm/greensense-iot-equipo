import pandas as pd
import pytest

import comun
from tests.generador import guardar, lecturas


@pytest.fixture
def cargar(tmp_path):
    def _cargar(**opciones):
        ruta = tmp_path / "lecturas_prueba.csv"
        guardar(lecturas(**opciones), ruta)
        return comun.cargar(ruta)

    return _cargar


def test_carga_el_csv_de_la_app_en_hora_local_y_sin_repetidas(tmp_path):
    ruta = tmp_path / "x.csv"
    datos = lecturas(horas=1)
    guardar(pd.concat([datos, datos.iloc[[0]]]), ruta)

    cargados = comun.cargar(ruta)

    assert len(cargados) == 60
    assert cargados.index.is_monotonic_increasing
    assert str(cargados.index.tz) == comun.ZONA
    assert cargados.index[0].hour == 0
    assert list(cargados.columns)[0] == "nodo"


def test_sin_archivos_lo_dice_con_instrucciones(tmp_path, monkeypatch):
    monkeypatch.delenv("GS_CSV", raising=False)
    monkeypatch.setattr(comun, "AQUI", tmp_path)
    with pytest.raises(FileNotFoundError, match="exporta las lecturas"):
        comun.ruta_de_datos()


def test_calidad_sin_perdidas(cargar):
    cal = comun.calidad(cargar(horas=2))
    assert (cal.lecturas, cal.esperadas, cal.perdidas) == (120, 120, 0)
    assert cal.horas == pytest.approx(119 / 60)
    assert cal.huecos.empty


def test_calidad_cuenta_las_perdidas_y_los_huecos(cargar):
    cal = comun.calidad(cargar(horas=2, sin_minutos=range(30, 40)))

    assert cal.perdidas == 10
    assert cal.porcentaje_perdidas == pytest.approx(100 * 10 / 120)
    assert len(cal.huecos) == 1
    assert cal.huecos.iloc[0]["minutos"] == 11


def test_un_hueco_corto_no_es_hueco_pero_si_perdida(cargar):
    cal = comun.calidad(cargar(horas=1, sin_minutos=range(10, 11)))
    assert cal.perdidas == 1
    assert cal.huecos.empty


def test_estadisticas_omiten_la_variable_sin_datos(cargar):
    tabla = comun.estadisticas(cargar(horas=2, sustrato="ninguno"))
    assert list(tabla.index) == [comun.NOMBRES["temperatura"], comun.NOMBRES["humedad_aire"]]


def test_tiempo_en_rango_suma_cien(cargar):
    tabla = comun.tiempo_en_rango(cargar())
    assert tabla.sum(axis=1).to_numpy() == pytest.approx(100, abs=0.2)


def test_ciclo_diario_tiene_su_maximo_por_la_tarde(cargar):
    ciclo = comun.ciclo_diario(cargar(), "temperatura")
    assert len(ciclo) == 24
    assert 13 <= ciclo["promedio"].idxmax() <= 17


def test_usa_el_sustrato_si_varia(cargar):
    assert comun.elegir_objetivo(cargar()) == "humedad_sustrato"


@pytest.mark.parametrize("sustrato", ["cero", "ninguno"])
def test_plan_b_si_el_sustrato_no_sirve(cargar, sustrato):
    assert comun.elegir_objetivo(cargar(sustrato=sustrato)) == "temperatura"


def test_sin_variacion_no_inventa_un_objetivo(cargar):
    datos = cargar(sustrato="cero")
    datos["temperatura"] = 20.0
    with pytest.raises(ValueError, match="no hay nada que predecir"):
        comun.elegir_objetivo(datos)


def test_el_objetivo_es_el_valor_futuro_y_no_se_filtra(cargar):
    datos = cargar(horas=6)
    x, y = comun.matriz_de_regresion(datos, "humedad_sustrato", horizonte_min=60, paso_min=5)

    rejilla = datos["humedad_sustrato"].resample("5min").median()
    momento = x.index[0]
    assert y.loc[momento] == rejilla.loc[momento + pd.Timedelta(minutes=60)]
    assert x.loc[momento, "actual"] == rejilla.loc[momento]
    assert x.loc[momento, "hace_1h"] == rejilla.loc[momento - pd.Timedelta(minutes=60)]
    assert "humedad_sustrato" not in x.columns


def test_no_rellena_los_huecos(cargar):
    datos = cargar(horas=12, sin_minutos=range(300, 420))
    x, y = comun.matriz_de_regresion(datos, "humedad_sustrato")

    hueco = pd.Timestamp("2026-11-07 05:30", tz=comun.ZONA)
    assert hueco not in x.index
    assert x.notna().all(axis=None) and y.notna().all()


def test_divide_en_el_tiempo_con_separacion(cargar):
    x, y = comun.matriz_de_regresion(cargar(), "humedad_sustrato")

    x_e, x_p, y_e, y_p = comun.dividir_en_el_tiempo(x, y, separacion_min=60)

    assert len(x_e) == len(y_e) and len(x_p) == len(y_p)
    assert x_p.index[0] - x_e.index[-1] > pd.Timedelta(minutes=60)
