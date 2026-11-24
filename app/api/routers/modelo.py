from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, TODOS, requiere_roles
from app.data import ml_engine
from app.data.database import get_db
from app.data.models import ModeloML, Usuario
from app.schemas import ModeloOut, ModeloRegistrar
from app.services import auditoria, prediccion as srv

router = APIRouter(prefix="/modelo", tags=["Modelo de Machine Learning"])


@router.get("/activo", response_model=ModeloOut)
def activo(db: Session = Depends(get_db), _: Usuario = Depends(requiere_roles(*TODOS))):
    return srv.modelo_activo(db)


@router.get("/activo/detalle", summary="Metadatos completos del modelo activo (comparación, importancia de variables)")
def detalle(db: Session = Depends(get_db), _: Usuario = Depends(requiere_roles(*TODOS))):
    modelo = srv.modelo_activo(db)
    try:
        meta = ml_engine.leer_metadatos(ml_engine.resolver_ruta(modelo.ruta_archivo))
    except ml_engine.ModeloNoDisponible as exc:
        raise HTTPException(409, str(exc))
    meta.pop("valores_referencia", None)
    return meta


@router.get("", response_model=list[ModeloOut], summary="Modelos registrados en la base de datos")
def registrados(db: Session = Depends(get_db), _: Usuario = Depends(requiere_roles(ADMIN))):
    return list(db.scalars(select(ModeloML).order_by(ModeloML.fecha_entrenamiento.desc())))


@router.get("/disponibles", summary="Modelos entrenados encontrados en la carpeta ml/models")
def disponibles(_: Usuario = Depends(requiere_roles(ADMIN))):
    return ml_engine.listar_disponibles()


@router.post("/registrar", response_model=ModeloOut, status_code=201)
def registrar(datos: ModeloRegistrar, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_roles(ADMIN))):
    modelo = srv.registrar_modelo(db, datos.archivo, datos.activar, admin)
    auditoria.registrar(db, admin.id, "registrar_modelo", "modelos_ml", modelo.id)
    db.commit()
    return modelo


@router.post("/{modelo_id}/activar", response_model=ModeloOut)
def activar(modelo_id: int, db: Session = Depends(get_db), admin: Usuario = Depends(requiere_roles(ADMIN))):
    modelo = db.get(ModeloML, modelo_id)
    if not modelo:
        raise HTTPException(404, "Modelo no encontrado")
    srv.activar_modelo(db, modelo)
    auditoria.registrar(db, admin.id, "activar_modelo", "modelos_ml", modelo.id)
    db.commit()
    return modelo
