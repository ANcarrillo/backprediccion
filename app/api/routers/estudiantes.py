from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, COORDINADOR, TODOS, requiere_roles
from app.data.database import get_db
from app.data.models import Usuario
from app.schemas import (
    EstudianteActualizar, EstudianteCrear, EstudianteOut, FichaEstudiante, PaginaEstudiantes,
)
from app.services import auditoria
from app.services import estudiantes as srv

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"])


@router.get("", response_model=PaginaEstudiantes)
def listar(q: str | None = Query(None, description="Código, documento o nombre"),
           programa_id: int | None = None, semestre: int | None = None, estado: str | None = None,
           nivel_riesgo: Literal["bajo", "medio", "alto", "sin_prediccion"] | None = None,
           orden: Literal["nombre", "riesgo"] = "nombre",
           pagina: int = Query(1, ge=1), por_pagina: int = Query(20, ge=1, le=200),
           db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    total, items = srv.listar(db, usuario, q, programa_id, semestre, estado, nivel_riesgo, orden, pagina, por_pagina)
    return PaginaEstudiantes(total=total, pagina=pagina, por_pagina=por_pagina, items=items)


@router.post("", response_model=EstudianteOut, status_code=201)
def crear(datos: EstudianteCrear, db: Session = Depends(get_db),
          usuario: Usuario = Depends(requiere_roles(ADMIN, COORDINADOR))):
    est = srv.crear(db, datos, usuario)
    auditoria.registrar(db, usuario.id, "crear", "estudiantes", est.id)
    db.commit()
    return srv.a_salida(est, None)


@router.get("/{estudiante_id}", response_model=EstudianteOut)
def obtener(estudiante_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    return srv.ficha(db, estudiante_id, usuario)["estudiante"]


@router.get("/{estudiante_id}/ficha", response_model=FichaEstudiante,
            summary="Ficha completa: académicos, socioeconómicos, predicciones, alertas e intervenciones")
def ficha(estudiante_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    datos = srv.ficha(db, estudiante_id, usuario)
    auditoria.registrar(db, usuario.id, "consultar", "estudiantes", estudiante_id)
    db.commit()
    return datos


@router.put("/{estudiante_id}", response_model=EstudianteOut)
def actualizar(estudiante_id: int, datos: EstudianteActualizar, db: Session = Depends(get_db),
               usuario: Usuario = Depends(requiere_roles(ADMIN, COORDINADOR))):
    srv.actualizar(db, estudiante_id, datos, usuario)
    auditoria.registrar(db, usuario.id, "actualizar", "estudiantes", estudiante_id,
                        datos.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    return srv.ficha(db, estudiante_id, usuario)["estudiante"]
