"""Mide los indicadores de éxito de la propuesta contra un servidor en marcha.

python medir_indicadores.py --url http://localhost:8000 --correo ana@ejemplo.com --nodo maceta1 \
    --desde 2026-11-07 --hasta 2026-11-10 --lecturas 10

Pide la contraseña sin mostrarla (o la toma de GS_CONTRASENA). No necesita instalar nada. El
tiempo de la notificación en el teléfono se mide a mano: este programa no ve el teléfono.
"""

import argparse
import getpass
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

ZONA = timezone(timedelta(hours=-6))
DIAS_MINIMOS = 7
PERDIDA_MAXIMA = 5.0
LATENCIA_MAXIMA_S = 10.0


@dataclass(frozen=True)
class Resultado:
    indicador: str
    medido: str
    cumple: bool | None
    """None: no se pudo medir."""


def dias(desde: date, hasta: date) -> list[date]:
    """Los días del periodo, incluidos los dos extremos."""
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


def inicio_de(dia: date) -> str:
    return datetime(dia.year, dia.month, dia.day, tzinfo=ZONA).isoformat()


def evaluar_perdida(resumen: dict) -> Resultado:
    porcentaje = resumen["porcentaje_perdidas"]
    if porcentaje is None or not resumen["esperadas"]:
        return Resultado("Lecturas perdidas < 5 %", "sin lecturas en el periodo", None)
    medido = f"{porcentaje:.2f} % ({resumen['lecturas']} de {resumen['esperadas']})"
    return Resultado("Lecturas perdidas < 5 %", medido, porcentaje < PERDIDA_MAXIMA)


def evaluar_duracion(resumen: dict, periodo_s: int) -> Resultado:
    """La duración real con datos, no la que se pidió: un periodo vacío no cuenta."""
    medido_dias = resumen["lecturas"] * periodo_s / 86_400
    return Resultado(
        "Al menos 7 días de prueba", f"{medido_dias:.1f} días de lecturas", medido_dias >= DIAS_MINIMOS
    )


def evaluar_dias(por_dia: dict[date, int]) -> Resultado:
    vacios = [d.isoformat() for d, n in por_dia.items() if n == 0]
    medido = f"{len(por_dia) - len(vacios)} de {len(por_dia)} días con lecturas"
    if vacios:
        medido += f"; sin datos: {', '.join(vacios)}"
    return Resultado("Reconstruir cualquier día del periodo", medido, not vacios and bool(por_dia))


def evaluar_latencia(latencias: list[float]) -> Resultado:
    if not latencias:
        return Resultado("Del sensor al panel < 10 s", "no llegaron lecturas", None)
    medido = (
        f"mediana {statistics.median(latencias):.2f} s, máximo {max(latencias):.2f} s "
        f"({len(latencias)} lecturas)"
    )
    return Resultado("Del sensor al panel < 10 s", medido, max(latencias) < LATENCIA_MAXIMA_S)


def latencia_de(evento: dict, nodo: str, ahora: datetime) -> float | None:
    """Segundos entre la hora de la lectura y su llegada; None si es de otro nodo o vieja.

    La hora la pone el nodo, sincronizado por NTP. Una lectura reenviada desde la cola no
    describe el tiempo real: se descarta si tiene más de un minuto.
    """
    if evento["nodo"]["id"] != nodo:
        return None
    ts = datetime.fromisoformat(evento["lectura"]["ts"].replace("Z", "+00:00"))
    segundos = (ahora - ts).total_seconds()
    return segundos if segundos < 60 else None


def leer_eventos(lineas):
    """Convierte las líneas de un flujo SSE en pares (evento, datos)."""
    tipo, datos = None, []
    for linea in lineas:
        linea = linea.decode("utf-8").rstrip("\r\n")
        if not linea:
            if tipo and datos:
                yield tipo, "\n".join(datos)
            tipo, datos = None, []
        elif linea.startswith("event:"):
            tipo = linea[6:].strip()
        elif linea.startswith("data:"):
            datos.append(linea[5:].strip())


class Api:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/") + "/api/v1"
        self.token: str | None = None

    def pedir(self, ruta: str, parametros: dict | None = None, cuerpo: dict | None = None):
        consulta = f"?{urllib.parse.urlencode(parametros)}" if parametros else ""
        encabezados = {"Content-Type": "application/json"}
        if self.token:
            encabezados["Authorization"] = f"Bearer {self.token}"
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        pedido = urllib.request.Request(self.url + ruta + consulta, datos, encabezados)
        with urllib.request.urlopen(pedido, timeout=60) as respuesta:
            return json.load(respuesta)

    def medir_latencia(self, nodo: str, cantidad: int, limite_s: float) -> list[float]:
        consulta = urllib.parse.urlencode({"token": self.token})
        latencias: list[float] = []
        fin = time.monotonic() + limite_s
        try:
            with urllib.request.urlopen(f"{self.url}/eventos?{consulta}", timeout=limite_s) as flujo:
                for tipo, datos in leer_eventos(flujo):
                    if tipo == "lectura":
                        latencia = latencia_de(json.loads(datos), nodo, datetime.now(UTC))
                        if latencia is not None:
                            latencias.append(latencia)
                    if len(latencias) >= cantidad or time.monotonic() > fin:
                        break
        except TimeoutError:
            pass
        return latencias


def medir(api: Api, nodo: str, desde: date, hasta: date, lecturas: int) -> list[Resultado]:
    fin = inicio_de(hasta + timedelta(days=1))
    rango = {"nodo": nodo, "desde": inicio_de(desde), "hasta": fin}
    resumen = api.pedir("/reportes/resumen", rango)
    periodo = next(n["periodo_s"] for n in api.pedir("/nodos") if n["id"] == nodo)
    por_dia = {}
    for dia in dias(desde, hasta):
        un_dia = {
            "nodo": nodo,
            "desde": inicio_de(dia),
            "hasta": inicio_de(dia + timedelta(days=1)),
        }
        por_dia[dia] = api.pedir("/reportes/resumen", un_dia)["lecturas"]
    # Con cada lectura por minuto, se espera un poco más de lo necesario.
    limite = max(120.0, (lecturas + 2) * periodo)
    latencias = [] if lecturas <= 0 else api.medir_latencia(nodo, lecturas, limite)
    return [
        evaluar_duracion(resumen, periodo),
        evaluar_perdida(resumen),
        evaluar_dias(por_dia),
        evaluar_latencia(latencias),
    ]


def imprimir(resultados: list[Resultado]) -> None:
    etiquetas = {True: "CUMPLE", False: "NO CUMPLE", None: "SIN MEDIR"}
    for r in resultados:
        print(f"{etiquetas[r.cumple]:<10} {r.indicador}: {r.medido}")
    print("A MANO     Notificación en el teléfono < 1 min: ver analisis/README.md")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--correo", required=True)
    parser.add_argument("--nodo", required=True)
    parser.add_argument("--desde", type=date.fromisoformat, required=True)
    parser.add_argument("--hasta", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--lecturas", type=int, default=10, help="lecturas para medir la latencia; 0: no medirla"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.desde > args.hasta:
        print("--desde debe ser anterior o igual a --hasta", file=sys.stderr)
        return 2
    contrasena = os.environ.get("GS_CONTRASENA") or getpass.getpass("Contraseña: ")
    api = Api(args.url)
    try:
        api.token = api.pedir(
            "/auth/login", cuerpo={"correo": args.correo, "contrasena": contrasena}
        )["token"]
        imprimir(medir(api, args.nodo, args.desde, args.hasta, args.lecturas))
    except urllib.error.HTTPError as error:
        print(f"El servidor respondió {error.code} en {error.url}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"No se pudo conectar con {args.url}: {error.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
