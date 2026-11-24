from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, TODOS, programas_visibles, requiere_roles
from app.data.database import get_db
from app.data.models import Alerta, Estudiante, Intervencion, Usuario
from app.schemas import IntervencionActualizar, IntervencionCrear, IntervencionOut
from app.services import auditoria
from app.services import estudiantes as srv_est

router = APIRouter(prefix="/intervenciones", tags=["Intervenciones"])


@router.get("", response_model=list[IntervencionOut])
def listar(estudiante_id: int | None = None, alerta_id: int | None = None, estado: str | None = None,
           db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    consulta = select(Intervencion).join(Estudiante, Estudiante.id == Intervencion.estudiante_id)
    visibles = programas_visibles(usuario)
    if visibles is not None:
        consulta = consulta.where(Estudiante.programa_id.in_(visibles))
    if estudiante_id:
        consulta = consulta.where(Intervencion.estudiante_id == estudiante_id)
    if alerta_id:
        consulta = consulta.where(Intervencion.alerta_id == alerta_id)
    if estado:
        consulta = consulta.where(Intervencion.estado == estado)
    return list(db.scalars(consulta.order_by(Intervencion.fecha.desc(), Intervencion.id.desc()).limit(500)).unique())


@router.post("", response_model=IntervencionOut, status_code=201)
def crear(datos: IntervencionCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    srv_est.obtener(db, datos.estudiante_id, usuario)
    if datos.alerta_id:
        alerta = db.get(Alerta, datos.alerta_id)
        if not alerta or alerta.estudiante_id != datos.estudiante_id:
            raise HTTPException(400, "La alerta no existe o no pertenece al estudiante")
        if alerta.estado == "pendiente":
            alerta.estado = "en_proceso"
    responsable_id = datos.responsable_id or usuario.id
    if not db.get(Usuario, responsable_id):
        raise HTTPException(400, "El responsable no existe")
    valores = datos.model_dump(exclude={"responsable_id"})
    valores["fecha"] = valores["fecha"] or date.today()
    intervencion = Intervencion(**valores, responsable_id=responsable_id)
    db.add(intervencion)
    db.flush()
    auditoria.registrar(db, usuario.id, "crear", "intervenciones", intervencion.id)
    db.commit()
    db.refresh(intervencion)
    return intervencion


@router.put("/{intervencion_id}", response_model=IntervencionOut)
def actualizar(intervencion_id: int, datos: IntervencionActualizar, db: Session = Depends(get_db),
               usuario: Usuario = Depends(requiere_roles(*TODOS))):
    intervencion = db.get(Intervencion, intervencion_id)
    if not intervencion:
        raise HTTPException(404, "Intervención no encontrada")
    srv_est.obtener(db, intervencion.estudiante_id, usuario)
    if intervencion.responsable_id != usuario.id and usuario.rol.nombre != ADMIN:
        raise HTTPException(403, "Solo el responsable o un administrador pueden modificarla")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(intervencion, campo, valor)
    auditoria.registrar(db, usuario.id, "actualizar", "intervenciones", intervencion.id)
    db.commit()
    db.refresh(intervencion)
    return intervencion
