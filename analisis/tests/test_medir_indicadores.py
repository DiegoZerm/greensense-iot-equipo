from datetime import UTC, date, datetime, timedelta

import medir_indicadores as m


def resumen(lecturas, esperadas, porcentaje):
    return {"lecturas": lecturas, "esperadas": esperadas, "porcentaje_perdidas": porcentaje}


def test_dias_incluye_los_dos_extremos():
    assert m.dias(date(2026, 11, 7), date(2026, 11, 9)) == [
        date(2026, 11, 7),
        date(2026, 11, 8),
        date(2026, 11, 9),
    ]


def test_inicio_del_dia_en_la_hora_del_invernadero():
    assert m.inicio_de(date(2026, 11, 7)) == "2026-11-07T00:00:00-06:00"


def test_72_horas_no_cumplen_los_7_dias_aunque_no_se_pierda_nada():
    r = m.evaluar_duracion(resumen(4320, 4320, 0.0), 60)
    assert r.cumple is False
    assert "3.0 días" in r.medido


def test_7_dias_cumplen():
    assert m.evaluar_duracion(resumen(10080, 10080, 0.0), 60).cumple is True


def test_perdida_al_borde_de_la_meta():
    assert m.evaluar_perdida(resumen(95, 100, 5.0)).cumple is False
    assert m.evaluar_perdida(resumen(96, 100, 4.0)).cumple is True


def test_perdida_sin_lecturas_no_cuenta_como_cumplida():
    assert m.evaluar_perdida(resumen(0, 0, None)).cumple is None


def test_dia_vacio_impide_reconstruir():
    r = m.evaluar_dias({date(2026, 11, 7): 1440, date(2026, 11, 8): 0})
    assert r.cumple is False
    assert "2026-11-08" in r.medido


def test_latencia():
    assert m.evaluar_latencia([]).cumple is None
    assert m.evaluar_latencia([1.0, 2.0]).cumple is True
    assert m.evaluar_latencia([1.0, 10.0]).cumple is False


def evento(nodo, ts):
    return {"nodo": {"id": nodo}, "lectura": {"ts": ts.isoformat().replace("+00:00", "Z")}}


def test_latencia_de_descarta_otros_nodos_y_lecturas_reenviadas():
    ahora = datetime(2026, 11, 7, 12, tzinfo=UTC)
    assert m.latencia_de(evento("n1", ahora - timedelta(seconds=2)), "n1", ahora) == 2
    assert m.latencia_de(evento("n2", ahora), "n1", ahora) is None
    assert m.latencia_de(evento("n1", ahora - timedelta(hours=1)), "n1", ahora) is None


def test_leer_eventos_ignora_comentarios():
    lineas = [
        b": conectado\n",
        b"retry: 5000\n",
        b"\n",
        b"event: lectura\n",
        b'data: {"a": 1}\n',
        b"\n",
    ]
    assert list(m.leer_eventos(lineas)) == [("lectura", '{"a": 1}')]
