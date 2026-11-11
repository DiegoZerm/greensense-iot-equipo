"""Línea de comandos del servidor: migraciones y alta de invernaderos y nodos.

greensense migrar
greensense invernadero agregar invernadero1 "Invernadero de prueba"
greensense nodo agregar invernadero1 nodo1 "Nodo junto a la puerta" --sensor-aire DHT11
greensense nodo listar
greensense usuario agregar ana@ejemplo.com "Ana López" --rol administrador
greensense usuario listar
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config as ConfigAlembic

from greensense.adaptadores.salida.postgres import (
    RepositorioBitacoraPostgres,
    RepositorioCultivosPostgres,
    RepositorioInvernaderosPostgres,
    RepositorioNodosPostgres,
    RepositorioUsuariosPostgres,
    crear_motor,
)
from greensense.adaptadores.salida.reloj import RelojSistema
from greensense.adaptadores.salida.seguridad import HasherArgon2
from greensense.adaptadores.salida.webpush import generar_claves_vapid
from greensense.aplicacion.casos_uso.bitacora import Anotador
from greensense.aplicacion.casos_uso.gestionar_nodos import RegistrarInvernadero, RegistrarNodo
from greensense.aplicacion.casos_uso.gestionar_usuarios import CrearUsuario
from greensense.aplicacion.errores import Conflicto, InvernaderoNoRegistrado, NoEncontrado
from greensense.config import Config
from greensense.dominio.modelos import SensorAire
from greensense.dominio.usuarios import Rol

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def migrar(url: str | None = None) -> None:
    configuracion = ConfigAlembic(str(ALEMBIC_INI))
    if url:
        configuracion.attributes["url"] = url
    command.upgrade(configuracion, "head")


async def _ejecutar(argumentos: argparse.Namespace, config: Config) -> None:
    motor = crear_motor(config.url_db)
    invernaderos = RepositorioInvernaderosPostgres(motor)
    nodos = RepositorioNodosPostgres(motor)
    usuarios = RepositorioUsuariosPostgres(motor)
    reloj = RelojSistema()
    # Lo que se hace desde aquí queda en la bitácora sin usuario (lo hizo el sistema).
    anotador = Anotador(RepositorioBitacoraPostgres(motor), reloj)
    try:
        match argumentos.recurso, argumentos.accion:
            case "invernadero", "agregar":
                registrar = RegistrarInvernadero(
                    invernaderos, RepositorioCultivosPostgres(motor), anotador
                )
                invernadero = await registrar.ejecutar(argumentos.id, argumentos.nombre)
                print(f"Invernadero {invernadero.id} registrado")
            case "nodo", "agregar":
                nodo = await RegistrarNodo(invernaderos, nodos, anotador).ejecutar(
                    argumentos.invernadero,
                    argumentos.id,
                    argumentos.nombre,
                    SensorAire(argumentos.sensor_aire),
                    argumentos.sensor_suelo,
                )
                print(f"Nodo {nodo.id} registrado en {nodo.invernadero_id}")
            case "nodo", "listar":
                for nodo in sorted(await nodos.listar(), key=lambda n: n.id):
                    suelo = "con suelo" if nodo.sensor_suelo else "sin suelo"
                    print(
                        f"{nodo.invernadero_id}/{nodo.id}  {nodo.nombre}  "
                        f"{nodo.sensor_aire} {suelo}  {nodo.estado}"
                        + ("" if nodo.activo else "  (de baja)")
                    )
            case "usuario", "agregar":
                contrasena = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
                crear = CrearUsuario(usuarios, HasherArgon2(), reloj, anotador)
                usuario = await crear.ejecutar(
                    None, argumentos.nombre, argumentos.correo, Rol(argumentos.rol), contrasena
                )
                print(f"Usuario {usuario.correo} ({usuario.rol}) registrado")
            case "usuario", "listar":
                for usuario in await usuarios.listar():
                    estado = "" if usuario.activo else "  (inactivo)"
                    print(
                        f"{usuario.id}  {usuario.correo}  {usuario.nombre}  {usuario.rol}{estado}"
                    )
    finally:
        await motor.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="greensense")
    recursos = parser.add_subparsers(dest="recurso", required=True)

    recursos.add_parser("migrar", help="aplica las migraciones pendientes")
    recursos.add_parser("vapid", help="genera las claves para las notificaciones push")

    invernadero = recursos.add_parser("invernadero").add_subparsers(dest="accion", required=True)
    agregar_invernadero = invernadero.add_parser("agregar")
    agregar_invernadero.add_argument("id")
    agregar_invernadero.add_argument("nombre")

    nodo = recursos.add_parser("nodo").add_subparsers(dest="accion", required=True)
    agregar_nodo = nodo.add_parser("agregar")
    agregar_nodo.add_argument("invernadero")
    agregar_nodo.add_argument("id")
    agregar_nodo.add_argument("nombre")
    agregar_nodo.add_argument(
        "--sensor-aire", choices=[s.value for s in SensorAire], default="DHT11"
    )
    agregar_nodo.add_argument("--sensor-suelo", action="store_true")
    nodo.add_parser("listar")

    usuario = recursos.add_parser("usuario").add_subparsers(dest="accion", required=True)
    agregar_usuario = usuario.add_parser("agregar", help="pide la contraseña sin mostrarla")
    agregar_usuario.add_argument("correo")
    agregar_usuario.add_argument("nombre")
    agregar_usuario.add_argument("--rol", choices=[r.value for r in Rol], default="operador")
    usuario.add_parser("listar")
    return parser


def main(argv: list[str] | None = None) -> None:
    argumentos = _parser().parse_args(argv)
    if argumentos.recurso == "migrar":
        migrar()
        return
    if argumentos.recurso == "vapid":
        privada, publica = generar_claves_vapid()
        print("# Agregar a infra/.env:")
        print(f"VAPID_PRIVADA={privada}")
        print(f"VAPID_PUBLICA={publica}")
        return
    try:
        asyncio.run(_ejecutar(argumentos, Config()))
    except (ValueError, InvernaderoNoRegistrado, NoEncontrado, Conflicto) as error:
        sys.exit(f"Error: {error}")


if __name__ == "__main__":
    main()
