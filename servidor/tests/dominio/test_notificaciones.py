from datetime import timedelta

from greensense.dominio.notificaciones import MAXIMO_INTENTOS, espera_tras_fallo


def test_espera_crece_al_doble():
    esperas = [espera_tras_fallo(n) for n in range(1, MAXIMO_INTENTOS)]

    assert esperas == [timedelta(seconds=s) for s in (30, 60, 120, 240, 480)]
