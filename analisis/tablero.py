"""Tablero de la prueba de campo: avance, pérdidas, huecos, valores y riegos.

.venv/bin/streamlit run tablero.py

Lee el servidor por su API, igual que medir_indicadores.py, y se actualiza solo cada minuto.
Los riegos se anotan aquí y quedan en datos/riegos.csv para el análisis.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import comun
from medir_indicadores import Api

AQUI = Path(__file__).resolve().parent
RIEGOS = AQUI / "datos" / "riegos.csv"
ZONA = comun.ZONA
SERIE = "#2a78d6"
FRANJA = "#f0efec"
MARCA_RIEGO = "#898781"
HORAS_PRUEBA = 72
PERIODO_S = 60

# --- Cálculos (sin Streamlit, para poder probarlos) --------------------------------------


def a_tabla(lecturas: list[dict]) -> pd.DataFrame:
    """Las lecturas de la API con el mismo formato que el CSV de la app."""
    if not lecturas:
        return pd.DataFrame(columns=["arranque", "seq", *comun.VARIABLES])
    datos = pd.DataFrame(lecturas)
    datos["fecha_hora"] = pd.to_datetime(datos["ts"], utc=True).dt.tz_convert(ZONA)
    datos = datos.set_index("fecha_hora").sort_index()
    return datos[~datos.index.duplicated()].drop(columns=["ts"])


def avance(inicio: pd.Timestamp, ahora: pd.Timestamp, horas: int = HORAS_PRUEBA) -> float:
    """Fracción de la prueba que ya pasó, entre 0 y 1."""
    return min(max((ahora - inicio) / pd.Timedelta(hours=horas), 0.0), 1.0)


def esperadas_hasta(inicio: pd.Timestamp, ahora: pd.Timestamp, periodo_s: int = PERIODO_S) -> int:
    """Lecturas que debieron llegar desde el inicio, aunque no haya llegado ninguna.

    Solo cuentan los periodos completos: la lectura del minuto en curso todavía no se debe.
    """
    return max(int((ahora - inicio).total_seconds() // periodo_s), 0)


def leer_riegos(ruta: Path = RIEGOS) -> pd.Series:
    if not ruta.exists():
        return pd.Series([], dtype=f"datetime64[ns, {ZONA}]", name="fecha_hora")
    tabla = pd.read_csv(ruta)
    return pd.to_datetime(tabla["fecha_hora"]).dt.tz_convert(ZONA).sort_values()


def anotar_riego(cuando: pd.Timestamp, ruta: Path = RIEGOS) -> None:
    ruta.parent.mkdir(exist_ok=True)
    nuevo = not ruta.exists()
    with ruta.open("a", encoding="utf-8") as archivo:
        if nuevo:
            archivo.write("fecha_hora\n")
        archivo.write(cuando.isoformat() + "\n")


# --- Página ------------------------------------------------------------------------------


def conectar() -> Api | None:
    """Prueba la URL elegida; si no responde, prueba la del despliegue con Docker."""
    with st.sidebar:
        st.header("Conexión")
        url = st.text_input("Servidor", os.environ.get("GS_URL", "http://localhost:8000"))
        correo = st.text_input("Correo", os.environ.get("GS_CORREO", ""))
        contrasena = st.text_input(
            "Contraseña", os.environ.get("GS_CONTRASENA", ""), type="password"
        )
    if not (correo and contrasena):
        st.info("Escribe tu correo y tu contraseña de la app en la barra lateral.")
        return None
    for candidata in dict.fromkeys([url, "http://localhost:8080"]):
        api = Api(candidata)
        try:
            api.token = api.pedir(
                "/auth/login", cuerpo={"correo": correo, "contrasena": contrasena}
            )["token"]
            if candidata != url:
                st.sidebar.caption(f"Conectado a {candidata}")
            return api
        except Exception as error:  # noqa: BLE001 - se muestra al final
            ultimo = error
    st.error(f"No se pudo entrar al servidor: {ultimo}")
    return None


def tarjeta(columna, etiqueta: str, valor: str, detalle: str = "") -> None:
    columna.metric(etiqueta, valor, help=detalle or None)
    if detalle:
        columna.caption(detalle)


def grafica(datos: pd.DataFrame, variable: str, riegos: pd.Series, inicio, fin) -> alt.Chart:
    # Mediana cada 5 minutos; donde faltan lecturas queda vacío y la línea se corta.
    serie = datos[variable].astype(float).resample("5min").median().rename("valor").reset_index()
    serie["fecha_hora"] = serie["fecha_hora"].dt.tz_localize(None)
    minimo, maximo = comun.RANGOS[variable]
    eje_x = alt.X(
        "fecha_hora:T",
        title=None,
        scale=alt.Scale(domain=[inicio.tz_localize(None), fin.tz_localize(None)]),
        axis=alt.Axis(format="%d %b %H:%M", labelColor="#52514e", gridColor="#e6e5e1"),
    )
    valores = serie["valor"].dropna()
    bajo = min(minimo, valores.min()) if not valores.empty else minimo
    alto = max(maximo, valores.max()) if not valores.empty else maximo
    margen = (alto - bajo) * 0.08 or 1
    eje_y = alt.Y(
        "valor:Q",
        title=comun.NOMBRES[variable],
        scale=alt.Scale(domain=[bajo - margen, alto + margen], nice=False, zero=False),
        axis=alt.Axis(labelColor="#52514e", titleColor="#52514e", gridColor="#e6e5e1"),
    )
    franja = (
        alt.Chart(pd.DataFrame({"minimo": [minimo], "maximo": [maximo]}))
        .mark_rect(color=FRANJA)
        .encode(y="minimo:Q", y2="maximo:Q")
    )
    linea = (
        alt.Chart(serie)
        .mark_line(color=SERIE, strokeWidth=2)
        .encode(
            x=eje_x,
            y=eje_y,
            tooltip=[
                alt.Tooltip("fecha_hora:T", title="Hora", format="%d %b %H:%M"),
                alt.Tooltip("valor:Q", title=comun.NOMBRES[variable], format=".1f"),
            ],
        )
    )
    capas = [franja, linea]
    if not riegos.empty:
        marcas = pd.DataFrame({"fecha_hora": riegos.dt.tz_localize(None).to_numpy()})
        capas.append(
            alt.Chart(marcas)
            .mark_rule(color=MARCA_RIEGO, strokeDash=[4, 3])
            .encode(x="fecha_hora:T", tooltip=[alt.Tooltip("fecha_hora:T", title="Riego")])
        )
    return alt.layer(*capas).properties(height=190)


def main() -> None:
    st.set_page_config(page_title="Prueba de campo · GreenSense", layout="wide")
    st.title("Prueba de campo")

    with st.sidebar:
        st.header("Prueba")
        nodo = st.text_input("Nodo", os.environ.get("GS_NODO", "maceta1"))
        dia = st.date_input("Inicio", datetime(2026, 11, 7).date())
        hora = st.time_input("Hora de inicio", datetime(2026, 11, 7, 17, 31).time(), step=60)
        horas = st.number_input("Duración (horas)", 1, 24 * 14, HORAS_PRUEBA)

    api = conectar()
    if api is None:
        return
    inicio = pd.Timestamp(datetime.combine(dia, hora), tz=ZONA)
    fin = inicio + pd.Timedelta(hours=horas)

    with st.sidebar:
        st.header("Riegos")
        st.caption("Anota cada riego: sirve para entender el sustrato en el análisis.")
        hace = st.number_input("Hace cuántos minutos", 0, 24 * 60, 0, step=5)
        if st.button("Anotar riego"):
            anotar_riego(pd.Timestamp.now(tz=ZONA).floor("min") - pd.Timedelta(minutes=hace))
            st.success("Riego anotado")

    @st.fragment(run_every=timedelta(seconds=60))
    def actualizar() -> None:
        ahora = pd.Timestamp.now(tz=ZONA)
        hasta = min(ahora, fin) + pd.Timedelta(minutes=1)
        try:
            serie = api.pedir(
                "/lecturas",
                {"nodo": nodo, "desde": inicio.isoformat(), "hasta": hasta.isoformat()},
            )
            activas = api.pedir("/alertas", {"activas": "true"})
        except Exception as error:  # noqa: BLE001 - el servidor puede estar apagado
            st.error(f"No se pudo consultar el servidor: {error}")
            return
        datos = a_tabla(serie["lecturas"])
        riegos = leer_riegos()
        riegos = riegos[(riegos >= inicio) & (riegos <= fin)]

        # Avance y calidad.
        fraccion = avance(inicio, ahora, horas)
        horas_pasadas = fraccion * horas
        if ahora < inicio:
            st.info(f"La prueba empieza el {inicio:%d/%m a las %H:%M}.")
        elif fraccion >= 1:
            st.success(f"Prueba terminada el {fin:%d/%m a las %H:%M}.")
        st.progress(
            fraccion,
            text=f"{horas_pasadas:.1f} de {horas} horas · termina el {fin:%d/%m a las %H:%M}",
        )
        esperadas = esperadas_hasta(inicio, min(ahora, fin))
        recibidas = len(datos)
        perdidas = 100 * max(esperadas - recibidas, 0) / esperadas if esperadas else 0.0
        if esperadas < 60:
            st.caption("Con menos de una hora de prueba, el porcentaje de pérdidas todavía varía mucho.")

        c1, c2, c3, c4 = st.columns(4)
        tarjeta(c1, "Lecturas", f"{recibidas:,}", f"de {esperadas:,} esperadas")
        tarjeta(
            c2,
            "Perdidas",
            f"{perdidas:.2f} %",
            "meta: menos de 5 %" + (" · se cumple" if perdidas < 5 else " · NO se cumple"),
        )
        if datos.empty:
            tarjeta(c3, "Última lectura", "sin lecturas")
        else:
            ultima = datos.index[-1]
            minutos = (ahora - ultima).total_seconds() / 60
            estado = "al día" if minutos < 5 else "el nodo no está mandando"
            tarjeta(c3, "Última lectura", f"hace {minutos:.0f} min", f"{ultima:%d/%m %H:%M} · {estado}")
        reinicios = datos["arranque"].nunique() - 1 if not datos.empty else 0
        tarjeta(c4, "Riegos anotados", str(len(riegos)), f"reinicios del nodo: {reinicios}")

        if datos.empty:
            st.warning("Todavía no hay lecturas en el periodo de la prueba.")
            return

        # Valores actuales: el número y su estado en texto, no solo con color.
        st.subheader("Ahora")
        columnas = st.columns(len(comun.VARIABLES))
        for columna, variable in zip(columnas, comun.VARIABLES, strict=True):
            valores = datos[variable].dropna()
            if valores.empty:
                columna.metric(comun.NOMBRES[variable], "sin datos")
                continue
            valor = valores.iloc[-1]
            minimo, maximo = comun.RANGOS[variable]
            estado = (
                "debajo del rango" if valor < minimo else "arriba del rango" if valor > maximo else "en rango"
            )
            columna.metric(comun.NOMBRES[variable], f"{valor:.1f}", help=f"rango {minimo:g}–{maximo:g}")
            columna.caption(f"{estado} ({minimo:g}–{maximo:g})")

        st.subheader("Desde el inicio de la prueba")
        st.caption(
            "Mediana cada 5 minutos. Franja gris: rango adecuado del cultivo. "
            "Líneas punteadas: riegos anotados. Los cortes son lecturas que faltan."
        )
        for variable in comun.VARIABLES:
            if datos[variable].notna().any():
                st.altair_chart(grafica(datos, variable, riegos, inicio, fin), use_container_width=True)

        izquierda, derecha = st.columns(2)
        with izquierda:
            st.subheader("Huecos de más de 3 minutos")
            huecos = comun.calidad(datos, PERIODO_S).huecos
            if huecos.empty:
                st.write("Ninguno.")
            else:
                st.dataframe(huecos, hide_index=True)
        with derecha:
            st.subheader("Alertas activas del nodo")
            del_nodo = [a for a in activas if a["nodo_id"] == nodo]
            if not del_nodo:
                st.write("Ninguna.")
            for alerta in del_nodo:
                st.write(f"**{alerta['severidad'].capitalize()}:** {alerta['mensaje']}")

        st.caption(f"Actualizado a las {ahora:%H:%M:%S}. Se actualiza solo cada minuto.")

    actualizar()


if __name__ == "__main__":
    main()
