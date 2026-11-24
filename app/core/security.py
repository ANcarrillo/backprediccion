"""Autenticación: contraseñas con bcrypt y tokens JWT."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def crear_token(usuario_id: int, rol: str) -> str:
    s = get_settings()
    expira = datetime.now(timezone.utc) + timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES)
    datos = {"sub": str(usuario_id), "rol": rol, "exp": expira}
    return jwt.encode(datos, s.SECRET_KEY, algorithm=s.ALGORITMO_JWT)


def decodificar_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.SECRET_KEY, algorithms=[s.ALGORITMO_JWT])
