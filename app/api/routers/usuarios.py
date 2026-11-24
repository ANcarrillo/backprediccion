from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, TODOS, requiere_roles
from app.data.database import get_db
from app.data.models import Rol, Usuario
from app.schemas import RolOut, UsuarioActualizar, UsuarioCrear, UsuarioMini, UsuarioOut
from app.services import auditoria, usuarios

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("", response_model=list[UsuarioOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(requiere_roles(ADMIN))):
    return list(db.scalars(select(Usuario).order_by(Usuario.apellidos)).unique())


@router.get("/responsables", response_model=list[UsuarioMini], summary="Usuarios activos para asignar alertas")
def responsables(db: Session = Depends(get_db), _: Usuario = Depends(requiere_roles(*TODOS))):
    return list(db.scalars(select(Usuario).where(Usuario.activo.is_(True)).order_by(Usuario.apellidos)).unique())


@router.get("/roles", response_model=list[RolOut])
def roles(db: Session = Depends(get_db), _: Usuario = Depends(requiere_roles(ADMIN))):
    return list(db.scalars(select(Rol).order_by(Rol.id)))


@router.post("", response_model=UsuarioOut, status_code=201)
def crear(datos: UsuarioCrear, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_roles(ADMIN))):
    usuario = usuarios.crear(db, datos)
    auditoria.registrar(db, admin.id, "crear", "usuarios", usuario.id)
    db.commit()
    return usuario


@router.put("/{usuario_id}", response_model=UsuarioOut)
def actualizar(usuario_id: int, datos: UsuarioActualizar, db: Session = Depends(get_db),
               admin: Usuario = Depends(requiere_roles(ADMIN))):
    usuario = usuarios.actualizar(db, usuario_id, datos)
    auditoria.registrar(db, admin.id, "actualizar", "usuarios", usuario.id,
                        {k: v for k, v in datos.model_dump(exclude_unset=True).items() if k != "password"})
    db.commit()
    return usuario
