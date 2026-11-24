"""Capa 3 - Predicción de riesgo (ML): construir variables, predecir, clasificar y alertar."""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import programas_visibles
from app.core.config import get_settings
from app.data import ml_engine
from app.data.models import (
    DatoAcademico, DatoSocioeconomico, Estudiante, ModeloML, PeriodoAcademico, Prediccion, Usuario,
)

from . import alertas as srv_alertas
from .errores import Conflicto, ErrorNegocio, NoEncontrado

NOMBRES_VARIABLES = {
    "edad": "Edad", "puntaje_saber11": "Puntaje Saber 11", "semestre_cursado": "Semestre",
    "creditos_inscritos": "Créditos inscritos", "creditos_aprobados": "Créditos aprobados",
    "creditos_reprobados": "Créditos reprobados", "tasa_aprobacion": "Tasa de aprobación",
    "promedio_periodo": "Promedio del periodo", "promedio_acumulado": "Promedio acumulado",
    "asistencia_pct": "Asistencia (%)", "materias_reprobadas": "Materias reprobadas",
    "materias_canceladas": "Materias canceladas", "materias_repetidas": "Materias repetidas",
    "estrato": "Estrato", "ingreso_familiar": "Ingreso familiar", "trabaja": "Trabaja",
    "horas_trabajo_semana": "Horas de trabajo/semana", "personas_a_cargo": "Personas a cargo",
    "distancia_km": "Distancia a la sede (km)", "tiene_beca": "Tiene beca",
    "apoyo_financiero": "Apoyo financiero", "tipo_colegio": "Tipo de colegio",
    "tipo_vivienda": "Tipo de vivienda", "zona_residencia": "Zona de residencia",
    "nivel_educativo_padres": "Nivel educativo de los padres",
}


def nivel_riesgo(probabilidad: float) -> str:
    s = get_settings()
    if probabilidad >= s.UMBRAL_RIESGO_ALTO:
        return "alto"
    if probabilidad >= s.UMBRAL_RIESGO_MEDIO:
        return "medio"
    return "bajo"


def _edad(nacimiento: date | None, referencia: date) -> int | None:
    if not nacimiento:
        return None
    return referencia.year - nacimiento.year - ((referencia.month, referencia.day) < (nacimiento.month, nacimiento.day))


def construir_variables(db: Session, est: Estudiante) -> tuple[dict, int] | None:
    """Mismas variables que la vista vw_dataset_desercion: último periodo académico
    del estudiante + datos socioeconómicos más cercanos. None si no hay datos académicos."""
    acad = db.scalar(select(DatoAcademico).join(PeriodoAcademico)
                     .where(DatoAcademico.estudiante_id == est.id)
                     .order_by(PeriodoAcademico.fecha_inicio.desc()).limit(1))
    if not acad:
        return None
    inicio = acad.periodo.fecha_inicio
    socios = list(db.scalars(select(DatoSocioeconomico).join(PeriodoAcademico)
                             .where(DatoSocioeconomico.estudiante_id == est.id)
                             .order_by(PeriodoAcademico.fecha_inicio.desc())))
    socio = next((s for s in socios if s.periodo.fecha_inicio <= inicio), socios[0] if socios else None)

    fila = {
        "edad": _edad(est.fecha_nacimiento, inicio),
        "genero": est.genero,
        "puntaje_saber11": est.puntaje_saber11,
        "tipo_colegio": est.tipo_colegio,
        "semestre_cursado": acad.semestre_cursado,
        "creditos_inscritos": acad.creditos_inscritos,
        "creditos_aprobados": acad.creditos_aprobados,
        "creditos_reprobados": acad.creditos_reprobados,
        "tasa_aprobacion": round(acad.creditos_aprobados / acad.creditos_inscritos, 4)
                           if acad.creditos_inscritos else None,
        "promedio_periodo": acad.promedio_periodo,
        "promedio_acumulado": acad.promedio_acumulado,
        "asistencia_pct": acad.asistencia_pct,
        "materias_reprobadas": acad.materias_reprobadas,
        "materias_canceladas": acad.materias_canceladas,
        "materias_repetidas": acad.materias_repetidas,
    }
    campos_socio = ["estrato", "ingreso_familiar", "trabaja", "horas_trabajo_semana", "personas_a_cargo",
                    "tipo_vivienda", "zona_residencia", "distancia_km", "tiene_beca", "apoyo_financiero",
                    "nivel_educativo_padres"]
    for campo in campos_socio:
        fila[campo] = getattr(socio, campo) if socio else None
    return fila, acad.periodo_id


# ---------------- Modelo activo ----------------
def modelo_activo(db: Session) -> ModeloML:
    modelo = db.scalar(select(ModeloML).where(ModeloML.activo.is_(True)))
    if not modelo:
        raise Conflicto("No hay un modelo de ML activo. Entrene uno en ml/ y regístrelo en /modelo/registrar")
    return modelo


def _motor(modelo: ModeloML) -> ml_engine.MotorML:
    try:
        return ml_engine.obtener_motor(modelo.ruta_archivo)
    except ml_engine.ModeloNoDisponible as exc:
        raise Conflicto(str(exc))


def registrar_modelo(db: Session, archivo: str, activar: bool, usuario: Usuario) -> ModeloML:
    ruta = ml_engine.resolver_ruta(archivo)
    if not ruta.exists() or ruta.suffix != ".pkl":
        raise NoEncontrado(f"No existe el archivo {archivo} en la carpeta de modelos")
    try:
        meta = ml_engine.leer_metadatos(ruta)
    except (ml_engine.ModeloNoDisponible, json.JSONDecodeError) as exc:
        raise ErrorNegocio(str(exc))
    existente = db.scalar(select(ModeloML).where(ModeloML.nombre == meta["nombre"],
                                                 ModeloML.version == meta["version"]))
    if existente:
        modelo = existente
    else:
        modelo = ModeloML(nombre=meta["nombre"], algoritmo=meta["algoritmo"], version=meta["version"],
                          ruta_archivo=archivo, metricas=meta.get("metricas"),
                          hiperparametros=meta.get("hiperparametros"), variables=meta.get("variables"),
                          registrado_por=usuario.id)
        db.add(modelo)
        db.flush()
    if activar:
        activar_modelo(db, modelo)
    return modelo


def activar_modelo(db: Session, modelo: ModeloML) -> None:
    _motor(modelo)  # verifica que el archivo cargue antes de activarlo
    db.execute(update(ModeloML).where(ModeloML.id != modelo.id).values(activo=False))
    db.flush()
    modelo.activo = True
    db.flush()


# ---------------- Predicción ----------------
def _guardar(db: Session, est_id: int, periodo_id: int, modelo: ModeloML, prob: float,
             factores: list[dict], usuario: Usuario) -> tuple[Prediccion, bool]:
    for f in factores:
        f["variable"] = NOMBRES_VARIABLES.get(f["variable"], f["variable"])
    pred = Prediccion(estudiante_id=est_id, periodo_id=periodo_id, modelo_id=modelo.id,
                      probabilidad=round(prob, 4), nivel_riesgo=nivel_riesgo(prob),
                      factores=factores, creado_por=usuario.id)
    db.add(pred)
    db.flush()
    alerta_nueva = False
    s = get_settings()
    if pred.nivel_riesgo == "alto" or (pred.nivel_riesgo == "medio" and s.ALERTA_RIESGO_MEDIO):
        principales = ", ".join(f["variable"] for f in factores[:3]) or "sin factores destacados"
        alerta_nueva = srv_alertas.crear_si_no_existe(
            db, est_id, "prediccion_ml", pred.nivel_riesgo,
            f"Riesgo {pred.nivel_riesgo} de deserción ({prob:.0%})",
            f"Predicción del modelo {modelo.algoritmo} v{modelo.version}. Factores principales: {principales}.",
            prediccion_id=pred.id) is not None
    return pred, alerta_nueva


def predecir_estudiante(db: Session, est: Estudiante, usuario: Usuario) -> Prediccion:
    modelo = modelo_activo(db)
    motor = _motor(modelo)
    construido = construir_variables(db, est)
    if not construido:
        raise ErrorNegocio("El estudiante no tiene datos académicos registrados; no se puede predecir")
    fila, periodo_id = construido
    X = motor.preparar([fila])
    prob = float(motor.probabilidades(X)[0])
    factores = motor.explicar(X)[0]
    pred, _ = _guardar(db, est.id, periodo_id, modelo, prob, factores, usuario)
    return pred


def predecir_lote(db: Session, usuario: Usuario, programa_id: int | None, solo_activos: bool) -> dict:
    modelo = modelo_activo(db)
    motor = _motor(modelo)
    consulta = select(Estudiante)
    visibles = programas_visibles(usuario)
    if visibles is not None:
        consulta = consulta.where(Estudiante.programa_id.in_(visibles))
    if programa_id:
        consulta = consulta.where(Estudiante.programa_id == programa_id)
    if solo_activos:
        consulta = consulta.where(Estudiante.estado == "activo")

    filas, ids, periodos, sin_datos = [], [], [], 0
    for est in db.scalars(consulta):
        construido = construir_variables(db, est)
        if not construido:
            sin_datos += 1
            continue
        filas.append(construido[0])
        ids.append(est.id)
        periodos.append(construido[1])

    resumen = {"procesados": 0, "sin_datos": sin_datos, "por_nivel": {"bajo": 0, "medio": 0, "alto": 0},
               "alertas_generadas": 0}
    if not filas:
        return resumen
    X = motor.preparar(filas)
    probs = motor.probabilidades(X)
    explicaciones = motor.explicar(X)
    for est_id, periodo_id, prob, factores in zip(ids, periodos, probs, explicaciones):
        pred, nueva = _guardar(db, est_id, periodo_id, modelo, float(prob), factores, usuario)
        resumen["procesados"] += 1
        resumen["por_nivel"][pred.nivel_riesgo] += 1
        resumen["alertas_generadas"] += int(nueva)
    return resumen
