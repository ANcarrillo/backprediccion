"""Pruebas con SQLite en memoria (no requieren PostgreSQL) y un modelo pequeño entrenado al vuelo."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.data.database import Base, get_db
from app.data.models import Rol
from app.main import app

NUM = ["promedio_periodo", "asistencia_pct", "materias_reprobadas", "estrato", "trabaja"]
CAT = ["zona_residencia"]


@pytest.fixture()
def modelo_dir(tmp_path):
    r = np.random.default_rng(0)
    n = 300
    df = pd.DataFrame({
        "promedio_periodo": r.uniform(1, 5, n), "asistencia_pct": r.uniform(40, 100, n),
        "materias_reprobadas": r.integers(0, 5, n), "estrato": r.integers(1, 6, n),
        "trabaja": r.integers(0, 2, n), "zona_residencia": r.choice(["urbana", "rural"], n),
    })
    y = ((df.promedio_periodo < 3) | (df.asistencia_pct < 60)).astype(int)
    pre = ColumnTransformer([("num", SimpleImputer(strategy="median"), NUM),
                             ("cat", Pipeline([("i", SimpleImputer(strategy="constant", fill_value="desconocido")),
                                               ("o", OneHotEncoder(handle_unknown="ignore"))]), CAT)])
    modelo = Pipeline([("pre", pre), ("clf", RandomForestClassifier(n_estimators=30, random_state=0))]).fit(df, y)
    joblib.dump(modelo, tmp_path / "modelo_prueba.pkl")
    meta = {"nombre": "modelo_prueba", "version": "1", "algoritmo": "random_forest", "archivo": "modelo_prueba.pkl",
            "metricas": {"f1": 0.9}, "hiperparametros": {}, "fecha_entrenamiento": "2026-01-01T00:00:00",
            "variables": {"numericas": NUM, "categoricas": CAT, "booleanas": ["trabaja"]},
            "valores_referencia": {"promedio_periodo": 3.5, "asistencia_pct": 85, "materias_reprobadas": 1,
                                   "estrato": 3, "trabaja": 0, "zona_residencia": "urbana"}}
    (tmp_path / "modelo_prueba.json").write_text(json.dumps(meta), encoding="utf-8")
    ajustes = get_settings()
    anterior = ajustes.MODELS_DIR
    ajustes.MODELS_DIR = str(tmp_path)
    yield tmp_path
    ajustes.MODELS_DIR = anterior


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sesion() as s:
        s.add_all([Rol(nombre=n) for n in ("administrador", "coordinador", "docente", "bienestar")])
        s.commit()
    yield Sesion
    engine.dispose()


@pytest.fixture()
def client(db_session, modelo_dir):
    def _db():
        s = db_session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    ajustes = get_settings()
    captcha_antes = ajustes.CAPTCHA_HABILITADO
    ajustes.CAPTCHA_HABILITADO = False  # las pruebas del CAPTCHA lo activan explícitamente
    with TestClient(app) as c:
        yield c
    ajustes.CAPTCHA_HABILITADO = captcha_antes
    app.dependency_overrides.clear()


@pytest.fixture()
def admin(client, db_session):
    from app.schemas import UsuarioCrear
    from app.services import usuarios
    with db_session() as s:
        usuarios.crear(s, UsuarioCrear(nombres="Ana", apellidos="Admin", email="admin@u.edu.co",
                                       password="Clave12345", rol="administrador"))
        s.commit()
    r = client.post("/auth/login", data={"username": "admin@u.edu.co", "password": "Clave12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
