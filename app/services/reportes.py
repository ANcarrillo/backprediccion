"""Capa 3 - Reportes e indicadores (estadísticas, seguimiento, exportar)."""
import csv
import io
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import programas_visibles
from app.data.models import Alerta, Estudiante, Intervencion, Prediccion, Programa, Usuario

from .estudiantes import ultima_prediccion_subq

NIVELES = ("bajo", "medio", "alto")


def _base(usuario: Usuario, programa_id: int | None):
    """Estudiantes activos con su última predicción (si existe)."""
    sub = ultima_prediccion_subq()
    consulta = (select(Estudiante, Prediccion)
                .outerjoin(sub, sub.c.estudiante_id == Estudiante.id)
                .outerjoin(Prediccion, Prediccion.id == sub.c.pid)
                .where(Estudiante.estado == "activo"))
    visibles = programas_visibles(usuario)
    if visibles is not None:
        consulta = consulta.where(Estudiante.programa_id.in_(visibles))
    if programa_id:
        consulta = consulta.where(Estudiante.programa_id == programa_id)
    return consulta


def resumen(db: Session, usuario: Usuario, programa_id: int | None = None) -> dict:
    filas = db.execute(_base(usuario, programa_id)).all()
    por_nivel = {n: 0 for n in NIVELES} | {"sin_prediccion": 0}
    for _, pred in filas:
        por_nivel[pred.nivel_riesgo if pred else "sin_prediccion"] += 1
    ids = [e.id for e, _ in filas]

    def contar(consulta):
        return db.scalar(consulta) or 0

    inicio_mes = date.today().replace(day=1)
    alertas_abiertas = contar(select(func.count(Alerta.id)).where(Alerta.estudiante_id.in_(ids),
                                                                  Alerta.estado.in_(("pendiente", "en_proceso"))))
    alertas_cerradas = contar(select(func.count(Alerta.id)).where(Alerta.estudiante_id.in_(ids),
                                                                  Alerta.estado.in_(("atendida", "cerrada"))))
    intervenciones_mes = contar(select(func.count(Intervencion.id)).where(Intervencion.estudiante_id.in_(ids),
                                                                         Intervencion.fecha >= inicio_mes))
    total_est = len(filas)
    return {
        "total_estudiantes": total_est,
        "por_nivel": por_nivel,
        "porcentaje_riesgo_alto": round(100 * por_nivel["alto"] / total_est, 1) if total_est else 0,
        "alertas_abiertas": alertas_abiertas,
        "alertas_cerradas": alertas_cerradas,
        "intervenciones_mes": intervenciones_mes,
    }


def riesgo_por(db: Session, usuario: Usuario, campo: str, programa_id: int | None = None) -> list[dict]:
    """Distribución de niveles de riesgo agrupada por 'programa' o 'semestre'."""
    grupos: dict = {}
    for est, pred in db.execute(_base(usuario, programa_id)).all():
        clave = est.programa.nombre if campo == "programa" else est.semestre_actual
        g = grupos.setdefault(clave, {"grupo": clave, "bajo": 0, "medio": 0, "alto": 0, "sin_prediccion": 0})
        g[pred.nivel_riesgo if pred else "sin_prediccion"] += 1
    return sorted(grupos.values(), key=lambda g: g["grupo"])


def evolucion(db: Session, usuario: Usuario, programa_id: int | None = None) -> list[dict]:
    """Promedio de probabilidad y casos de riesgo alto por mes (seguimiento)."""
    consulta = select(Prediccion).join(Estudiante, Estudiante.id == Prediccion.estudiante_id)
    visibles = programas_visibles(usuario)
    if visibles is not None:
        consulta = consulta.where(Estudiante.programa_id.in_(visibles))
    if programa_id:
        consulta = consulta.where(Estudiante.programa_id == programa_id)
    meses: dict[str, dict] = {}
    for p in db.scalars(consulta):
        clave = p.creado_en.strftime("%Y-%m")
        m = meses.setdefault(clave, {"mes": clave, "predicciones": 0, "suma": 0.0, "alto": 0})
        m["predicciones"] += 1
        m["suma"] += p.probabilidad
        m["alto"] += p.nivel_riesgo == "alto"
    return [{"mes": m["mes"], "predicciones": m["predicciones"], "alto": m["alto"],
             "probabilidad_promedio": round(m["suma"] / m["predicciones"], 4)}
            for m in sorted(meses.values(), key=lambda m: m["mes"])]


def exportar_csv(db: Session, usuario: Usuario, programa_id: int | None = None,
                 nivel: str | None = None) -> str:
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(["codigo", "documento", "nombres", "apellidos", "programa", "semestre",
                       "probabilidad", "nivel_riesgo", "fecha_prediccion", "factores_principales"])
    filas = db.execute(_base(usuario, programa_id).order_by(Prediccion.probabilidad.desc().nulls_last())).all()
    for est, pred in filas:
        if nivel and (not pred or pred.nivel_riesgo != nivel):
            continue
        factores = ", ".join(f["variable"] for f in (pred.factores or [])[:3]) if pred else ""
        escritor.writerow([est.codigo, est.numero_documento, est.nombres, est.apellidos, est.programa.nombre,
                           est.semestre_actual, f"{pred.probabilidad:.4f}" if pred else "",
                           pred.nivel_riesgo if pred else "sin_prediccion",
                           pred.creado_en.strftime("%Y-%m-%d %H:%M") if pred else "", factores])
    return "﻿" + salida.getvalue()   # BOM para que Excel abra bien las tildes


def nombre_archivo() -> str:
    return f"reporte_riesgo_{datetime.now():%Y%m%d_%H%M}.csv"
