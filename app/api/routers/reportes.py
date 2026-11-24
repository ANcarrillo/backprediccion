from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import TODOS, requiere_roles
from app.data.database import get_db
from app.data.models import Usuario
from app.services import auditoria, reportes as srv

router = APIRouter(prefix="/reportes", tags=["Reportes e indicadores"])
lectores = requiere_roles(*TODOS)


@router.get("/resumen", summary="Indicadores generales del dashboard")
def resumen(programa_id: int | None = None, db: Session = Depends(get_db), usuario: Usuario = Depends(lectores)):
    return srv.resumen(db, usuario, programa_id)


@router.get("/riesgo-por-programa")
def por_programa(db: Session = Depends(get_db), usuario: Usuario = Depends(lectores)):
    return srv.riesgo_por(db, usuario, "programa")


@router.get("/riesgo-por-semestre")
def por_semestre(programa_id: int | None = None, db: Session = Depends(get_db), usuario: Usuario = Depends(lectores)):
    return srv.riesgo_por(db, usuario, "semestre", programa_id)


@router.get("/evolucion", summary="Seguimiento mensual de las predicciones")
def evolucion(programa_id: int | None = None, db: Session = Depends(get_db), usuario: Usuario = Depends(lectores)):
    return srv.evolucion(db, usuario, programa_id)


@router.get("/exportar", summary="Exportar estudiantes y su nivel de riesgo (CSV para Excel)")
def exportar(programa_id: int | None = None, nivel: Literal["bajo", "medio", "alto"] | None = None,
             db: Session = Depends(get_db), usuario: Usuario = Depends(lectores)):
    contenido = srv.exportar_csv(db, usuario, programa_id, nivel)
    auditoria.registrar(db, usuario.id, "exportar", "reportes", None, {"programa_id": programa_id, "nivel": nivel})
    db.commit()
    return Response(contenido, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{srv.nombre_archivo()}"'})
