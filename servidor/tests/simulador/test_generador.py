from datetime import UTC, datetime, timedelta

from simulador.generador import ESCENARIOS, Generador

INICIO = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)  # 00:00 en Querétaro


def _dia(generador: Generador, paso_min: int = 10) -> list[dict]:
    return [generador.siguiente(INICIO + timedelta(minutes=m)) for m in range(0, 24 * 60, paso_min)]


def test_la_temperatura_mas_alta_es_por_la_tarde():
    lecturas = _dia(Generador(ESCENARIOS["normal"], semilla=1))

    mas_caliente = max(range(len(lecturas)), key=lambda i: lecturas[i]["temperatura"])
    hora_local = mas_caliente * 10 / 60
    assert 12 <= hora_local <= 18


def test_escenario_normal_se_mantiene_en_rango():
    for lectura in _dia(Generador(ESCENARIOS["normal"], semilla=2)):
        assert 15 <= lectura["temperatura"] <= 31
        assert 50 <= lectura["humedad_aire"] <= 90
        assert 40 <= lectura["humedad_sustrato"] <= 70


def test_escenario_calor_rebasa_28_grados():
    temperaturas = [lectura["temperatura"] for lectura in _dia(Generador(ESCENARIOS["calor"]))]

    assert max(temperaturas) > 28


def test_escenario_seco_baja_del_minimo_de_sustrato():
    sustrato = [lectura["humedad_sustrato"] for lectura in _dia(Generador(ESCENARIOS["seco"]))]

    assert sustrato[-1] < 45
    assert sustrato == sorted(sustrato, reverse=True) or sustrato[-1] < sustrato[0]


def test_dht11_entrega_enteros_y_sin_suelo_entrega_nulo():
    lectura = Generador(ESCENARIOS["normal"], "DHT11", sensor_suelo=False).siguiente(INICIO)

    assert lectura["temperatura"] == int(lectura["temperatura"])
    assert lectura["humedad_aire"] == int(lectura["humedad_aire"])
    assert lectura["humedad_sustrato"] is None


def test_misma_semilla_mismos_datos():
    assert _dia(Generador(ESCENARIOS["normal"], semilla=7)) == _dia(
        Generador(ESCENARIOS["normal"], semilla=7)
    )


def test_forzar_acepta_valores_y_null():
    from simulador.__main__ import _parser

    args = _parser().parse_args(
        ["--contrasena", "x", "--forzar", "temperatura=31", "--forzar", "humedad_sustrato=null"]
    )

    assert dict(args.forzar) == {"temperatura": 31.0, "humedad_sustrato": None}


def test_forzar_rechaza_variables_desconocidas():
    import pytest

    from simulador.__main__ import _parser

    with pytest.raises(SystemExit):
        _parser().parse_args(["--contrasena", "x", "--forzar", "presion=3"])
