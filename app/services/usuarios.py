"""Capa 3 - Gestión de usuarios y autenticación."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verificar_password
from app.data.models import Programa, Rol, Usuario
from app.schemas import UsuarioActualizar, UsuarioCrear

from .errores import Conflicto, ErrorNegocio, NoEncontrado


def autenticar(db: Session, email: str, password: str) -> Usuario | None:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email.lower().strip()))
    if not usuario or not usuario.activo or not verificar_password(password, usuario.password_hash):
        return None
    usuario.ultimo_acceso = datetime.now()
    return usuario


def _rol(db: Session, nombre: str) -> Rol:
    rol = db.scalar(select(Rol).where(Rol.nombre == nombre))
    if not rol:
        raise ErrorNegocio(f"El rol '{nombre}' no existe. ¿Ejecutó database/schema.sql?")
    return rol


def _programas(db: Session, ids: list[int]) -> list[Programa]:
    programas = list(db.scalars(select(Programa).where(Programa.id.in_(ids)))) if ids else []
    if len(programas) != len(set(ids)):
        raise ErrorNegocio("Alguno de los programas indicados no existe")
    return programas


def crear(db: Session, datos: UsuarioCrear) -> Usuario:
    email = datos.email.lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise Conflicto("Ya existe un usuario con ese correo")
    usuario = Usuario(nombres=datos.nombres, apellidos=datos.apellidos, email=email,
                      password_hash=hash_password(datos.password), rol=_rol(db, datos.rol),
                      programas=_programas(db, datos.programas_ids))
    db.add(usuario)
    db.flush()
    return usuario


def actualizar(db: Session, usuario_id: int, datos: UsuarioActualizar) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    cambios = datos.model_dump(exclude_unset=True)
    if "password" in cambios:
        usuario.password_hash = hash_password(cambios.pop("password"))
    if "rol" in cambios:
        usuario.rol = _rol(db, cambios.pop("rol"))
    if "programas_ids" in cambios:
        usuario.programas = _programas(db, cambios.pop("programas_ids") or [])
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    db.flush()
    return usuario
