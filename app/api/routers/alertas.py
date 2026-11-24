from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, BIENESTAR, COORDINADOR, TODOS, requiere_roles
from app.data.database import get_db
from app.data.models import Usuario
from app.schemas import AlertaActualizar, AlertaCrear, AlertaOut, PaginaAlertas
from app.services import alertas as srv
from app.services import auditoria
from app.services import estudiantes as srv_est

router = APIRouter(prefix="/alertas", tags=["Alertas"])
gestores = requiere_roles(ADMIN, COORDINADOR, BIENESTAR)


@router.get("", response_model=PaginaAlertas)
def listar(estado: str | None = Query(None, description="pendiente, en_proceso, atendida, cerrada o 'abiertas'"),
           nivel: str | None = None, tipo: str | None = None, estudiante_id: int | None = None,
           mias: bool = False, pagina: int = Query(1, ge=1), por_pagina: int = Query(20, ge=1, le=200),
           db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    total, items = srv.listar(db, usuario, estado, nivel, tipo, estudiante_id, mias, pagina, por_pagina)
    return PaginaAlertas(total=total, pagina=pagina, por_pagina=por_pagina, items=items)


@router.get("/{alerta_id}", response_model=AlertaOut)
def obtener(alerta_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    return srv.obtener(db, alerta_id, usuario)


@router.post("", response_model=AlertaOut, status_code=201, summary="Crear una alerta manual")
def crear(datos: AlertaCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    srv_est.obtener(db, datos.estudiante_id, usuario)
    alerta = srv.crear_manual(db, datos)
    auditoria.registrar(db, usuario.id, "crear", "alertas", alerta.id)
    db.commit()
    db.refresh(alerta)
    return alerta


@router.put("/{alerta_id}", response_model=AlertaOut, summary="Cambiar estado o responsable (notificar / seguimiento)")
def actualizar(alerta_id: int, datos: AlertaActualizar, db: Session = Depends(get_db),
               usuario: Usuario = Depends(gestores)):
    alerta = srv.actualizar(db, srv.obtener(db, alerta_id, usuario), datos)
    auditoria.registrar(db, usuario.id, "actualizar", "alertas", alerta.id, datos.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(alerta)
    return alerta
