from greensense import __version__


def test_salud_responde_ok_y_version(cliente):
    respuesta = cliente.get("/api/v1/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "version": __version__}
