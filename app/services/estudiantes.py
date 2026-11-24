"""Capa 3 - Gestión de estudiantes (crear, consultar, actualizar)."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import programas_visibles
from app.data.models import (
    Alerta, DatoAcademico, DatoSocioeconomico, Estudiante, Intervencion, PeriodoAcademico,
    Prediccion, Programa, Usuario,
)
from app.schemas import EstudianteActualizar, EstudianteCrear, EstudianteOut, RiesgoResumen

from .errores import Conflicto, ErrorNegocio, NoEncontrado, SinPermiso


def ultima_prediccion_subq():
    """Subconsulta: id de la predicción más reciente de cada estudiante."""
    return (select(Prediccion.estudiante_id, func.max(Prediccion.id).label("pid"))
            .group_by(Prediccion.estudiante_id).subquery())


def a_salida(est: Estudiante, pred: Prediccion | None) -> EstudianteOut:
    salida = EstudianteOut.model_validate(est)
    if pred:
        salida.riesgo = RiesgoResumen(probabilidad=pred.probabilidad, nivel_riesgo=pred.nivel_riesgo,
                                      fecha=pred.creado_en)
    return salida


def obtener(db: Session, estudiante_id: int, usuario: Usuario) -> Estudiante:
    est = db.get(Estudiante, estudiante_id)
    if not est:
        raise NoEncontrado("Estudiante no encontrado")
    visibles = programas_visibles(usuario)
    if visibles is not None and est.programa_id not in visibles:
        raise SinPermiso("El estudiante pertenece a un programa que usted no tiene asignado")
    return est


def listar(db: Session, usuario: Usuario, q: str | None = None, programa_id: int | None = None,
           semestre: int | None = None, estado: str | None = None, nivel_riesgo: str | None = None,
           orden: str = "nombre", pagina: int = 1, por_pagina: int = 20):
    sub = ultima_prediccion_subq()
    consulta = (select(Estudiante, Prediccion)
                .outerjoin(sub, sub.c.estudiante_id == Estudiante.id)
                .outerjoin(Prediccion, Prediccion.id == sub.c.pid))
    visibles = programas_visibles(usuario)
    if visibles is not None:
        consulta = consulta.where(Estudiante.programa_id.in_(visibles))
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.where(or_(Estudiante.codigo.ilike(patron), Estudiante.numero_documento.ilike(patron),
                                      Estudiante.nombres.ilike(patron), Estudiante.apellidos.ilike(patron)))
    if programa_id:
        consulta = consulta.where(Estudiante.programa_id == programa_id)
    if semestre:
        consulta = consulta.where(Estudiante.semestre_actual == semestre)
    if estado:
        consulta = consulta.where(Estudiante.estado == estado)
    if nivel_riesgo == "sin_prediccion":
        consulta = consulta.where(Prediccion.id.is_(None))
    elif nivel_riesgo:
        consulta = consulta.where(Prediccion.nivel_riesgo == nivel_riesgo)

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    if orden == "riesgo":
        consulta = consulta.order_by(Prediccion.probabilidad.desc().nulls_last(), Estudiante.apellidos)
    else:
        consulta = consulta.order_by(Estudiante.apellidos, Estudiante.nombres)
    filas = db.execute(consulta.offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    return total, [a_salida(e, p) for e, p in filas]


def _validar_referencias(db: Session, programa_id: int | None, periodo_id: int | None) -> None:
    if programa_id is not None and not db.get(Programa, programa_id):
        raise ErrorNegocio("El programa no existe")
    if periodo_id is not None and not db.get(PeriodoAcademico, periodo_id):
        raise ErrorNegocio("El periodo de ingreso no existe")


def crear(db: Session, datos: EstudianteCrear, usuario: Usuario) -> Estudiante:
    if db.scalar(select(Estudiante).where(or_(Estudiante.codigo == datos.codigo,
                                              Estudiante.numero_documento == datos.numero_documento))):
        raise Conflicto("Ya existe un estudiante con ese código o documento")
    _validar_referencias(db, datos.programa_id, datos.periodo_ingreso_id)
    visibles = programas_visibles(usuario)
    if visibles is not None and datos.programa_id not in visibles:
        raise SinPermiso("No puede registrar estudiantes en un programa que no tiene asignado")
    est = Estudiante(**datos.model_dump())
    db.add(est)
    db.flush()
    return est


def actualizar(db: Session, estudiante_id: int, datos: EstudianteActualizar, usuario: Usuario) -> Estudiante:
    est = obtener(db, estudiante_id, usuario)
    cambios = datos.model_dump(exclude_unset=True)
    if "numero_documento" in cambios and cambios["numero_documento"] != est.numero_documento:
        if db.scalar(select(Estudiante).where(Estudiante.numero_documento == cambios["numero_documento"])):
            raise Conflicto("Ya existe un estudiante con ese documento")
    _validar_referencias(db, cambios.get("programa_id"), cambios.get("periodo_ingreso_id"))
    for campo, valor in cambios.items():
        setattr(est, campo, valor)
    db.flush()
    return est


def ficha(db: Session, estudiante_id: int, usuario: Usuario) -> dict:
    est = obtener(db, estudiante_id, usuario)
    ultima = db.scalar(select(Prediccion).where(Prediccion.estudiante_id == est.id)
                       .order_by(Prediccion.id.desc()).limit(1))
    orden_periodo = PeriodoAcademico.fecha_inicio.desc()
    return {
        "estudiante": a_salida(est, ultima),
        "academicos": list(db.scalars(select(DatoAcademico).join(PeriodoAcademico)
                                      .where(DatoAcademico.estudiante_id == est.id).order_by(orden_periodo))),
        "socioeconomicos": list(db.scalars(select(DatoSocioeconomico).join(PeriodoAcademico)
                                           .where(DatoSocioeconomico.estudiante_id == est.id).order_by(orden_periodo))),
        "predicciones": list(db.scalars(select(Prediccion).where(Prediccion.estudiante_id == est.id)
                                        .order_by(Prediccion.id.desc()).limit(20))),
        "alertas": list(db.scalars(select(Alerta).where(Alerta.estudiante_id == est.id)
                                   .order_by(Alerta.id.desc()))),
        "intervenciones": list(db.scalars(select(Intervencion).where(Intervencion.estudiante_id == est.id)
                                          .order_by(Intervencion.fecha.desc(), Intervencion.id.desc()))),
    }
