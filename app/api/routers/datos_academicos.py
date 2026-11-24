from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, BIENESTAR, COORDINADOR, TODOS, requiere_roles
from app.data.database import get_db
from app.data.models import DatoAcademico, DatoSocioeconomico, PeriodoAcademico, Usuario
from app.schemas import (
    DatoAcademicoIn, DatoAcademicoOut, DatoSocioIn, DatoSocioOut, ResultadoImportacion,
)
from app.services import auditoria, datos as srv
from app.services import estudiantes as srv_est

router = APIRouter(prefix="/datos-academicos", tags=["Datos académicos y socioeconómicos"])
editores_acad = requiere_roles(ADMIN, COORDINADOR)
editores_socio = requiere_roles(ADMIN, COORDINADOR, BIENESTAR)


@router.get("", response_model=list[DatoAcademicoOut])
def listar_academicos(estudiante_id: int, db: Session = Depends(get_db),
                      usuario: Usuario = Depends(requiere_roles(*TODOS))):
    srv_est.obtener(db, estudiante_id, usuario)
    return list(db.scalars(select(DatoAcademico).join(PeriodoAcademico)
                           .where(DatoAcademico.estudiante_id == estudiante_id)
                           .order_by(PeriodoAcademico.fecha_inicio.desc())))


@router.post("", response_model=DatoAcademicoOut, status_code=201,
             summary="Registrar o actualizar el resumen académico de un periodo (aplica reglas de riesgo)")
def guardar_academico(datos: DatoAcademicoIn, db: Session = Depends(get_db), usuario: Usuario = Depends(editores_acad)):
    registro, nuevo, _ = srv.guardar_academico(db, datos, usuario)
    auditoria.registrar(db, usuario.id, "crear" if nuevo else "actualizar", "datos_academicos", registro.id)
    db.commit()
    return registro


@router.delete("/{registro_id}", status_code=204)
def eliminar_academico(registro_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(editores_acad)):
    srv.eliminar(db, DatoAcademico, registro_id, usuario)
    auditoria.registrar(db, usuario.id, "eliminar", "datos_academicos", registro_id)
    db.commit()


@router.get("/socioeconomicos", response_model=list[DatoSocioOut])
def listar_socio(estudiante_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    srv_est.obtener(db, estudiante_id, usuario)
    return list(db.scalars(select(DatoSocioeconomico).join(PeriodoAcademico)
                           .where(DatoSocioeconomico.estudiante_id == estudiante_id)
                           .order_by(PeriodoAcademico.fecha_inicio.desc())))


@router.post("/socioeconomicos", response_model=DatoSocioOut, status_code=201)
def guardar_socio(datos: DatoSocioIn, db: Session = Depends(get_db), usuario: Usuario = Depends(editores_socio)):
    registro, nuevo, _ = srv.guardar_socioeconomico(db, datos, usuario)
    auditoria.registrar(db, usuario.id, "crear" if nuevo else "actualizar", "datos_socioeconomicos", registro.id)
    db.commit()
    return registro


@router.delete("/socioeconomicos/{registro_id}", status_code=204)
def eliminar_socio(registro_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(editores_socio)):
    srv.eliminar(db, DatoSocioeconomico, registro_id, usuario)
    auditoria.registrar(db, usuario.id, "eliminar", "datos_socioeconomicos", registro_id)
    db.commit()


@router.post("/importar", response_model=ResultadoImportacion,
             summary="Carga masiva desde CSV (columnas: codigo_estudiante, periodo y campos del registro)")
async def importar(tipo: Literal["academicos", "socioeconomicos"], archivo: UploadFile = File(...),
                   db: Session = Depends(get_db), usuario: Usuario = Depends(editores_acad)):
    resultado = srv.importar_csv(db, await archivo.read(), tipo, usuario)
    auditoria.registrar(db, usuario.id, "importar", f"datos_{tipo}", None,
                        {k: v for k, v in resultado.items() if k != "errores"} | {"errores": len(resultado["errores"])})
    db.commit()
    return resultado
