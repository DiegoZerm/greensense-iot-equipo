from datetime import timedelta

import jwt
import pytest

from greensense.adaptadores.salida.seguridad import EmisorJwt, HasherArgon2
from greensense.aplicacion.puertos import TokenInvalido
from tests.fabricas import RelojFijo, crear_usuario

SECRETO = "s" * 40


def test_argon2_verifica_la_contrasena(hasher):
    guardado = hasher.generar("contrasena-1")

    assert guardado.startswith("$argon2id$")
    assert hasher.verificar(guardado, "contrasena-1")
    assert not hasher.verificar(guardado, "contrasena-2")
    assert not hasher.verificar("no-es-un-hash", "contrasena-1")


def test_argon2_usa_sal_distinta_cada_vez(hasher):
    assert hasher.generar("igual") != hasher.generar("igual")


def test_argon2_normal_tambien_funciona():
    hasher = HasherArgon2()
    assert hasher.verificar(hasher.generar("contrasena-1"), "contrasena-1")


def test_token_lleva_el_usuario_y_vence():
    reloj = RelojFijo()
    emisor = EmisorJwt(SECRETO, timedelta(hours=12), reloj)
    token = emisor.emitir(crear_usuario(id=7))

    assert emisor.leer(token) == 7
    reloj.actual += timedelta(hours=11, minutes=59)
    assert emisor.leer(token) == 7
    reloj.actual += timedelta(minutes=1)
    with pytest.raises(TokenInvalido):
        emisor.leer(token)


@pytest.mark.parametrize(
    "token",
    [
        "basura",
        jwt.encode({"sub": "7", "aud": "greensense", "exp": 4e9}, "otro" * 10, "HS256"),
        jwt.encode({"sub": "7", "aud": "otra-app", "exp": 4e9}, SECRETO, "HS256"),
        jwt.encode({"sub": "7", "aud": "greensense"}, SECRETO, "HS256"),
        jwt.encode({"sub": "no-num", "aud": "greensense", "exp": 4e9}, SECRETO, "HS256"),
    ],
    ids=["basura", "otra-firma", "otra-audiencia", "sin-vencimiento", "sub-invalido"],
)
def test_token_invalido(token):
    with pytest.raises(TokenInvalido):
        EmisorJwt(SECRETO, timedelta(hours=1), RelojFijo()).leer(token)


def test_algoritmo_none_se_rechaza():
    token = jwt.encode({"sub": "7", "aud": "greensense", "exp": 4e9}, None, algorithm="none")
    with pytest.raises(TokenInvalido):
        EmisorJwt(SECRETO, timedelta(hours=1), RelojFijo()).leer(token)


def test_secreto_corto_se_rechaza():
    with pytest.raises(ValueError):
        EmisorJwt("corto", timedelta(hours=1), RelojFijo())
