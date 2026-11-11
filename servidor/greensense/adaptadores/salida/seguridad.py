"""Contraseñas con Argon2 y tokens de sesión JWT firmados con HS256."""

from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from greensense.aplicacion.puertos import Reloj, TokenInvalido
from greensense.dominio.usuarios import Usuario


class HasherArgon2:
    """Argon2id con los parámetros recomendados por argon2-cffi (RFC 9106, perfil bajo
    en memoria). `rapido=True` es solo para las pruebas."""

    def __init__(self, rapido: bool = False) -> None:
        if rapido:
            self._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
        else:
            self._hasher = PasswordHasher()

    def generar(self, contrasena: str) -> str:
        return self._hasher.hash(contrasena)

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        try:
            return self._hasher.verify(hash_guardado, contrasena)
        except (VerificationError, InvalidHashError):
            return False


class EmisorJwt:
    ALGORITMO = "HS256"
    AUDIENCIA = "greensense"

    def __init__(self, secreto: str, duracion: timedelta, reloj: Reloj) -> None:
        if len(secreto) < 32:
            raise ValueError("el secreto JWT debe tener al menos 32 caracteres")
        self._secreto = secreto
        self._duracion = duracion
        self._reloj = reloj

    def emitir(self, usuario: Usuario) -> str:
        ahora = self._reloj.ahora()
        datos = {
            "sub": str(usuario.id),
            "aud": self.AUDIENCIA,
            "iat": ahora,
            "exp": ahora + self._duracion,
        }
        return jwt.encode(datos, self._secreto, algorithm=self.ALGORITMO)

    def leer(self, token: str) -> int:
        try:
            datos = jwt.decode(
                token,
                self._secreto,
                algorithms=[self.ALGORITMO],
                audience=self.AUDIENCIA,
                # El vencimiento se revisa con el reloj del servidor (puerto Reloj) y no
                # con el de la biblioteca, para poder probarlo con un reloj falso.
                options={"require": ["sub", "exp"], "verify_exp": False, "verify_iat": False},
            )
            usuario_id = int(datos["sub"])
            vence = float(datos["exp"])
        except (jwt.PyJWTError, ValueError, TypeError) as error:
            raise TokenInvalido(str(error)) from error
        if self._reloj.ahora().timestamp() >= vence:
            raise TokenInvalido("la sesión venció")
        return usuario_id
