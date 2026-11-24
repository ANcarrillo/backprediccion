from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, BIENESTAR, COORDINADOR, TODOS, requiere_roles
from app.data.database import get_db
from app.data.models import Prediccion, Usuario
from app.schemas import PrediccionLoteIn, PrediccionLoteOut, PrediccionOut
from app.services import auditoria, prediccion as srv
from app.services import estudiantes as srv_est

router = APIRouter(prefix="/predicciones", tags=["Predicciones de riesgo (ML)"])


@router.post("/estudiante/{estudiante_id}", response_model=PrediccionOut, status_code=201,
             summary="Predecir el riesgo de deserción de un estudiante")
def predecir(estudiante_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    est = srv_est.obtener(db, estudiante_id, usuario)
    pred = srv.predecir_estudiante(db, est, usuario)
    auditoria.registrar(db, usuario.id, "predecir", "estudiantes", est.id,
                        {"probabilidad": pred.probabilidad, "nivel": pred.nivel_riesgo})
    db.commit()
    return pred


@router.post("/lote", response_model=PrediccionLoteOut,
             summary="Predecir el riesgo de todos los estudiantes (opcionalmente de un programa)")
def predecir_lote(datos: PrediccionLoteIn, db: Session = Depends(get_db),
                  usuario: Usuario = Depends(requiere_roles(ADMIN, COORDINADOR, BIENESTAR))):
    resumen = srv.predecir_lote(db, usuario, datos.programa_id, datos.solo_activos)
    auditoria.registrar(db, usuario.id, "predecir_lote", "estudiantes", None, resumen)
    db.commit()
    return resumen


@router.get("", response_model=list[PrediccionOut], summary="Historial de predicciones de un estudiante")
def historial(estudiante_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere_roles(*TODOS))):
    srv_est.obtener(db, estudiante_id, usuario)
    return list(db.scalars(select(Prediccion).where(Prediccion.estudiante_id == estudiante_id)
                           .order_by(Prediccion.id.desc())))
