class NodoNoRegistrado(Exception):
    def __init__(self, invernadero_id: str, nodo_id: str) -> None:
        super().__init__(f"el nodo '{nodo_id}' no está registrado en '{invernadero_id}'")
        self.invernadero_id = invernadero_id
        self.nodo_id = nodo_id


class InvernaderoNoRegistrado(Exception):
    def __init__(self, invernadero_id: str) -> None:
        super().__init__(f"el invernadero '{invernadero_id}' no está registrado")
        self.invernadero_id = invernadero_id


class AlertaNoEncontrada(Exception):
    def __init__(self, alerta_id: int) -> None:
        super().__init__(f"no existe la alerta {alerta_id}")
        self.alerta_id = alerta_id


class NoEncontrado(Exception):
    """El recurso pedido no existe."""

    def __init__(self, recurso: str, identificador: object) -> None:
        super().__init__(f"no existe {recurso} '{identificador}'")


class Conflicto(Exception):
    """La operación dejaría el sistema en un estado inválido (duplicado, en uso, etc.)."""


class CorreoDuplicado(Conflicto):
    def __init__(self, correo: str) -> None:
        super().__init__(f"ya hay un usuario con el correo '{correo}'")


class CredencialesInvalidas(Exception):
    def __init__(self) -> None:
        super().__init__("correo o contraseña incorrectos")


class DatosInvalidos(ValueError):
    """Un dato enviado no cumple el formato o el rango permitido."""
