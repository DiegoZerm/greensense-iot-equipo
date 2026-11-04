"""Simula un nodo GreenSense publicando por MQTT.

gs-simulador --nodo nodo1 --contrasena clave1
gs-simulador --nodo nodo1 --contrasena clave1 --escenario calor --periodo 5
gs-simulador --nodo nodo1 --contrasena clave1 --historico 48   # 48 h de datos y termina
"""

import argparse
import asyncio
import contextlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta

import aiomqtt

from simulador.generador import ESCENARIOS, Generador

log = logging.getLogger("simulador")
VERSION = "sim-0.1"


VARIABLES = ("temperatura", "humedad_aire", "humedad_sustrato")


def _forzado(texto: str) -> tuple[str, float | None]:
    """Convierte 'temperatura=31' (o 'temperatura=null') en ('temperatura', 31.0)."""
    variable, _, valor = texto.partition("=")
    if variable not in VARIABLES or not valor:
        raise argparse.ArgumentTypeError(
            f"usar VARIABLE=VALOR con VARIABLE en {', '.join(VARIABLES)}"
        )
    if valor == "null":
        return variable, None
    try:
        return variable, float(valor)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"'{valor}' no es un número") from error


def _lectura(nodo: str, arranque: int, seq: int, ts: datetime, valores: dict) -> str:
    return json.dumps(
        {
            "v": 1,
            "nodo": nodo,
            "arranque": arranque,
            "seq": seq,
            "ts": ts.isoformat(timespec="seconds").replace("+00:00", "Z"),
            **valores,
            "muestras": 5,
            "rssi": -60,
        }
    )


async def simular(args: argparse.Namespace) -> None:
    base = f"greensense/{args.invernadero}/{args.nodo}"
    desconectado = json.dumps({"v": 1, "estado": "desconectado"})
    conectado = json.dumps(
        {
            "v": 1,
            "estado": "conectado",
            "arranque": args.arranque,
            "firmware": VERSION,
            "sensor_aire": args.sensor_aire,
            "sensor_suelo": not args.sin_suelo,
            "periodo_s": max(args.periodo, 5),
        }
    )
    generador = Generador(
        ESCENARIOS[args.escenario], args.sensor_aire, not args.sin_suelo, semilla=args.semilla
    )
    forzados = dict(args.forzar)

    def valores(ts: datetime) -> dict:
        return generador.siguiente(ts) | forzados

    async with aiomqtt.Client(
        args.host,
        args.puerto,
        username=args.nodo,
        password=args.contrasena,
        identifier=f"simulador-{args.nodo}",
        will=aiomqtt.Will(f"{base}/estado", desconectado, qos=1, retain=True),
    ) as cliente:
        await cliente.publish(f"{base}/estado", conectado, qos=1, retain=True)
        log.info("%s conectado (%s, arranque %s)", base, args.escenario, args.arranque)
        seq = 0
        try:
            if args.historico:
                periodo = timedelta(seconds=args.periodo)
                ts = datetime.now(UTC) - timedelta(hours=args.historico)
                while ts <= datetime.now(UTC):
                    carga = _lectura(args.nodo, args.arranque, seq, ts, valores(ts))
                    await cliente.publish(f"{base}/lecturas", carga, qos=1)
                    seq += 1
                    ts += periodo
                log.info("%s lecturas históricas publicadas", seq)
                return

            while args.cantidad is None or seq < args.cantidad:
                ts = datetime.now(UTC)
                carga = _lectura(args.nodo, args.arranque, seq, ts, valores(ts))
                await cliente.publish(f"{base}/lecturas", carga, qos=1)
                log.info("lectura %s: %s", seq, carga)
                seq += 1
                await asyncio.sleep(args.periodo)
        finally:
            # Desconexión ordenada: el broker no publica la última voluntad, así que
            # el simulador avisa por su cuenta, igual que el firmware.
            await cliente.publish(f"{base}/estado", desconectado, qos=1, retain=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gs-simulador", description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--puerto", type=int, default=1883)
    parser.add_argument("--invernadero", default="invernadero1")
    parser.add_argument("--nodo", default="nodo1", help="también es el usuario MQTT")
    parser.add_argument("--contrasena", required=True, help="contraseña MQTT del nodo")
    parser.add_argument("--escenario", choices=sorted(ESCENARIOS), default="normal")
    parser.add_argument("--periodo", type=float, default=60, help="segundos entre lecturas")
    parser.add_argument("--sensor-aire", choices=["DHT11", "DHT22"], default="DHT22")
    parser.add_argument(
        "--sin-suelo", action="store_true", help="simula un nodo sin sensor de suelo"
    )
    parser.add_argument("--cantidad", type=int, help="termina después de N lecturas")
    parser.add_argument("--historico", type=float, help="publica N horas hacia atrás y termina")
    parser.add_argument("--arranque", type=int, default=int(time.time()) % 1_000_000)
    parser.add_argument("--semilla", type=int)
    parser.add_argument(
        "--forzar",
        type=_forzado,
        action="append",
        default=[],
        metavar="VARIABLE=VALOR",
        help="fija una variable, por ejemplo temperatura=31 o humedad_sustrato=null",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    args = _parser().parse_args(argv)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(simular(args))


if __name__ == "__main__":
    main()
