from fastapi import APIRouter
from pydantic import BaseModel

from greensense import __version__

router = APIRouter(tags=["salud"])


class Salud(BaseModel):
    estado: str
    version: str


@router.get("/salud")
def consultar_salud() -> Salud:
    return Salud(estado="ok", version=__version__)
