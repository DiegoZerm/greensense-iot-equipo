"""Corre los notebooks completos, porque un error ahí solo se vería el día de usarlos."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.generador import guardar, lecturas

CARPETA = Path(__file__).resolve().parents[1] / "notebooks"


def ejecutar(nombre: str, csv: Path, salida: Path) -> str:
    resultado = salida / f"{nombre}.ipynb"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--output",
            str(resultado),
            str(CARPETA / f"{nombre}.ipynb"),
        ],
        check=True,
        cwd=CARPETA,
        capture_output=True,
        env={**os.environ, "GS_CSV": str(csv), "MPLBACKEND": "agg"},
        timeout=180,
    )
    celdas = json.loads(resultado.read_text(encoding="utf-8"))["cells"]
    textos = []
    for celda in celdas:
        for parte in celda.get("outputs", []):
            textos += parte.get("data", {}).get("text/markdown", [])
            textos += parte.get("text", [])
    return "".join(textos)


@pytest.fixture
def csv(tmp_path):
    def _csv(**opciones):
        ruta = tmp_path / "lecturas_prueba.csv"
        guardar(lecturas(**opciones), ruta)
        return ruta

    return _csv


@pytest.mark.parametrize("nombre", ["01_descriptivo", "02_regresion"])
def test_con_72_horas_corre_y_avisa_la_limitacion(nombre, csv, tmp_path):
    texto = ejecutar(nombre, csv(horas=72), tmp_path)
    assert "Limitación" in texto
    assert "3.0 días" in texto


def test_con_7_dias_no_avisa_limitacion(csv, tmp_path):
    assert "Limitación" not in ejecutar("01_descriptivo", csv(horas=170), tmp_path)


def test_regresion_usa_el_sustrato_y_da_un_veredicto(csv, tmp_path):
    texto = ejecutar("02_regresion", csv(), tmp_path)
    assert "Humedad del sustrato (%) dentro de 60 minutos" in texto
    assert "persistencia" in texto
    assert "Plan B" not in texto


def test_sustrato_en_cero_avisa_y_usa_el_plan_b(csv, tmp_path):
    ruta = csv(sustrato="cero")
    assert "el sustrato casi no varió" in ejecutar("01_descriptivo", ruta, tmp_path)
    assert "Plan B" in ejecutar("02_regresion", ruta, tmp_path)


def test_sin_sensor_de_suelo_tambien_corre(csv, tmp_path):
    ruta = csv(sustrato="ninguno")
    ejecutar("01_descriptivo", ruta, tmp_path)
    assert "Plan B" in ejecutar("02_regresion", ruta, tmp_path)


def test_sin_huecos_no_muestra_una_tabla_vacia(csv, tmp_path):
    assert "Empty DataFrame" not in ejecutar("01_descriptivo", csv(horas=24), tmp_path)
