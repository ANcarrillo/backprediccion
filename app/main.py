"""Punto de entrada de la API REST (Capa 2).

Ejecutar:  uvicorn app.main:app --reload
Documentación interactiva (Swagger / OpenAPI): http://localhost:8000/docs
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routers import (
    alertas, auth, catalogos, datos_academicos, estudiantes, intervenciones, modelo, predicciones,
    reportes, usuarios,
)
from app.core.config import get_settings
from app.services.errores import ErrorNegocio

settings = get_settings()

app = FastAPI(
    title=settings.APP_NOMBRE,
    version="1.0.0",
    description="Plataforma de identificación temprana de estudiantes en riesgo de deserción "
                "(Random Forest, Gradient Boosting, XGBoost, LightGBM).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_lista,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErrorNegocio)
async def error_negocio(_: Request, exc: ErrorNegocio):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensaje})


@app.exception_handler(IntegrityError)
async def error_integridad(_: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Conflicto con datos existentes o referencia inválida"})


for r in (auth, usuarios, catalogos, estudiantes, datos_academicos, predicciones, alertas,
          intervenciones, reportes, modelo):
    app.include_router(r.router)


@app.get("/", tags=["Estado"])
def raiz():
    return {"servicio": settings.APP_NOMBRE, "documentacion": "/docs"}


@app.get("/salud", tags=["Estado"])
def salud():
    from sqlalchemy import text
    from app.data.database import engine
    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1"))
        bd = "ok"
    except Exception as exc:  # noqa: BLE001
        bd = f"error: {exc.__class__.__name__}"
    return {"api": "ok", "base_de_datos": bd}
