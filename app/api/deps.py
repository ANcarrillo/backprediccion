"""Capa 2 - Dependencias comunes: sesión de BD, usuario autenticado y autorización por rol."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.security import decodificar_token
from app.data.database import get_db
from app.data.models import Usuario

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

ADMIN = "administrador"
COORDINADOR = "coordinador"
DOCENTE = "docente"
BIENESTAR = "bienestar"
TODOS = (ADMIN, COORDINADOR, DOCENTE, BIENESTAR)


def usuario_actual(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada",
                          headers={"WWW-Authenticate": "Bearer"})
    try:
        datos = decodificar_token(token)
        usuario_id = int(datos["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise error
    usuario = db.get(Usuario, usuario_id)
    if not usuario or not usuario.activo:
        raise error
    return usuario


def requiere_roles(*roles: str):
    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol.nombre not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permisos para esta acción")
        return usuario
    return verificar


def programas_visibles(usuario: Usuario) -> list[int] | None:
    """None = puede ver todos los programas. Coordinadores y docentes con programas
    asignados solo ven los estudiantes de esos programas."""
    if usuario.rol.nombre in (ADMIN, BIENESTAR) or not usuario.programas:
        return None
    return [p.id for p in usuario.programas]
