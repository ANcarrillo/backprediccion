"""Capa 4 - Inteligencia: carga el modelo entrenado (.pkl) y ejecuta predicciones.

El modelo y su archivo de metadatos (.json) los genera el proyecto ml/ (src/entrenar.py).
"""
from __future__ import annotations

import json
import math
import threading
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings


class ModeloNoDisponible(Exception):
    pass


class MotorML:
    def __init__(self, ruta_pkl: Path, metadatos: dict):
        self.ruta = ruta_pkl
        self.meta = metadatos
        self.pipeline = joblib.load(ruta_pkl)
        variables = metadatos["variables"]
        self.numericas: list[str] = variables["numericas"]
        self.categoricas: list[str] = variables["categoricas"]
        self.booleanas: list[str] = variables.get("booleanas", [])
        self.referencia: dict = metadatos.get("valores_referencia", {})

    @property
    def columnas(self) -> list[str]:
        return self.numericas + self.categoricas

    def preparar(self, filas: list[dict]) -> pd.DataFrame:
        """Mismo tratamiento que ml/src/datos.py -> preparar_variables."""
        df = pd.DataFrame(filas)
        for col in self.numericas:
            if col not in df:
                df[col] = np.nan
            if col in self.booleanas:
                df[col] = df[col].map(lambda v: np.nan if v is None else (1.0 if v else 0.0))
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
        for col in self.categoricas:
            if col not in df:
                df[col] = np.nan
            df[col] = df[col].map(lambda v: v.strip().lower() if isinstance(v, str) else np.nan).astype(object)
        return df[self.columnas]

    def probabilidades(self, X: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(X)[:, 1]

    def explicar(self, X: pd.DataFrame, top: int = 5) -> list[list[dict]]:
        """Explicabilidad local por perturbación: cuánto baja la probabilidad si la
        variable toma el valor típico (mediana / moda) de los datos de entrenamiento.
        Impacto positivo = la variable aumenta el riesgo del estudiante."""
        base = self.probabilidades(X)
        impactos = {}
        for col in self.columnas:
            if col not in self.referencia:
                continue
            X_mod = X.copy()
            X_mod[col] = self.referencia[col]
            impactos[col] = base - self.probabilidades(X_mod)
        resultado = []
        for i in range(len(X)):
            factores = []
            for col, imp in impactos.items():
                valor = X.iloc[i][col]
                if isinstance(valor, float) and math.isnan(valor):
                    valor = None
                elif isinstance(valor, (np.floating, np.integer)):
                    valor = float(valor)
                factores.append({"variable": col, "valor": valor,
                                 "referencia": self.referencia[col], "impacto": round(float(imp[i]), 4)})
            factores.sort(key=lambda f: f["impacto"], reverse=True)
            resultado.append([f for f in factores if f["impacto"] > 0][:top])
        return resultado


_cache: dict[str, MotorML] = {}
_lock = threading.Lock()


def resolver_ruta(ruta_archivo: str) -> Path:
    ruta = Path(ruta_archivo)
    return ruta if ruta.is_absolute() else get_settings().dir_modelos / ruta


def leer_metadatos(ruta_pkl: Path) -> dict:
    ruta_json = ruta_pkl.with_suffix(".json")
    if not ruta_json.exists():
        raise ModeloNoDisponible(f"No existe el archivo de metadatos {ruta_json.name}")
    return json.loads(ruta_json.read_text(encoding="utf-8"))


def obtener_motor(ruta_archivo: str) -> MotorML:
    ruta = resolver_ruta(ruta_archivo)
    clave = str(ruta)
    with _lock:
        if clave not in _cache:
            if not ruta.exists():
                raise ModeloNoDisponible(f"No se encontró el archivo del modelo: {ruta}")
            _cache[clave] = MotorML(ruta, leer_metadatos(ruta))
        return _cache[clave]


def listar_disponibles() -> list[dict]:
    """Modelos entrenados presentes en MODELS_DIR (pares .pkl + .json)."""
    carpeta = get_settings().dir_modelos
    if not carpeta.exists():
        return []
    salida = []
    for ruta_json in sorted(carpeta.glob("*.json"), reverse=True):
        try:
            meta = json.loads(ruta_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (carpeta / meta.get("archivo", "")).exists():
            salida.append({k: meta.get(k) for k in
                           ("nombre", "version", "algoritmo", "archivo", "fecha_entrenamiento", "metricas")})
    return salida
