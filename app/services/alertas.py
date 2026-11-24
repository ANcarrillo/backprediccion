"""Capa 3 - Gestión de alertas y reglas de riesgo."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import programas_visibles
from app.core.config import get_settings
from app.data.models import Alerta, DatoAcademico, DatoSocioeconomico, Estudiante, Usuario
from app.schemas import AlertaActualizar, AlertaCrear

from .errores import ErrorNegocio, NoEncontrado, SinPermiso

ABIERTAS = ("pendiente", "en_proceso")


def crear_si_no_existe(db: Session, estudiante_id: int, tipo: str, nivel: str, titulo: str,
                       descripcion: str | None = None, prediccion_id: int | None = None) -> Alerta | None:
    """Evita duplicados: si el estudiante ya tiene una alerta abierta del mismo tipo,
    solo la actualiza (sube el nivel si corresponde)."""
    abierta = db.scalar(select(Alerta).where(Alerta.estudiante_id == estudiante_id, Alerta.tipo == tipo,
                                             Alerta.estado.in_(ABIERTAS)))
    if abierta:
        if nivel == "alto" and abierta.nivel != "alto":
            abierta.nivel, abierta.titulo, abierta.descripcion = nivel, titulo, descripcion
        if prediccion_id:
            abierta.prediccion_id = prediccion_id
        return None
    alerta = Alerta(estudiante_id=estudiante_id, tipo=tipo, nivel=nivel, titulo=titulo,
                    descripcion=descripcion, prediccion_id=prediccion_id)
    db.add(alerta)
    db.flush()
    return alerta


def reglas_academicas(db: Session, dato: DatoAcademico) -> int:
    """Reglas de riesgo sobre los datos académicos de un periodo. Devuelve alertas nuevas."""
    s = get_settings()
    nuevas = 0
    motivos = []
    if dato.promedio_periodo is not None and dato.promedio_periodo < s.REGLA_PROMEDIO_MINIMO:
        motivos.append(f"promedio del periodo {dato.promedio_periodo:.2f} < {s.REGLA_PROMEDIO_MINIMO}")
    if dato.materias_reprobadas >= s.REGLA_MATERIAS_REPROBADAS:
        motivos.append(f"{dato.materias_reprobadas} materias reprobadas")
    if motivos:
        nivel = "alto" if len(motivos) > 1 else "medio"
        if crear_si_no_existe(db, dato.estudiante_id, "academica", nivel, "Bajo rendimiento académico",
                              "Regla académica: " + "; ".join(motivos)):
            nuevas += 1
    if dato.asistencia_pct is not None and dato.asistencia_pct < s.REGLA_ASISTENCIA_MINIMA:
        nivel = "alto" if dato.asistencia_pct < s.REGLA_ASISTENCIA_MINIMA - 15 else "medio"
        if crear_si_no_existe(db, dato.estudiante_id, "asistencia", nivel, "Baja asistencia",
                              f"Asistencia del {dato.asistencia_pct:.1f}% (mínimo {s.REGLA_ASISTENCIA_MINIMA}%)"):
            nuevas += 1
    return nuevas


def reglas_socioeconomicas(db: Session, dato: DatoSocioeconomico) -> int:
    s = get_settings()
    motivos = []
    if dato.trabaja and dato.horas_trabajo_semana >= s.REGLA_HORAS_TRABAJO:
        motivos.append(f"trabaja {dato.horas_trabajo_semana} h/semana")
    if dato.estrato is not None and dato.estrato <= 1 and not (dato.tiene_beca or dato.apoyo_financiero):
        motivos.append("estrato 0-1 sin beca ni apoyo financiero")
    if len(motivos) and crear_si_no_existe(db, dato.estudiante_id, "socioeconomica",
                                           "alto" if len(motivos) > 1 else "medio",
                                           "Condición socioeconómica de riesgo", "; ".join(motivos)):
        return 1
    return 0


def listar(db: Session, usuario: Usuario, estado: str | None = None, nivel: str | None = None,
           tipo: str | None = None, estudiante_id: int | None = None, mias: bool = False,
           pagina: int = 1, por_pagina: int = 20):
    consulta = select(Alerta).join(Estudiante, Estudiante.id == Alerta.estudiante_id)
    visibles = programas_visibles(usuario)
    if visibles is not None:
        consulta = consulta.where(Estudiante.programa_id.in_(visibles))
    if estado == "abiertas":
        consulta = consulta.where(Alerta.estado.in_(ABIERTAS))
    elif estado:
        consulta = consulta.where(Alerta.estado == estado)
    if nivel:
        consulta = consulta.where(Alerta.nivel == nivel)
    if tipo:
        consulta = consulta.where(Alerta.tipo == tipo)
    if estudiante_id:
        consulta = consulta.where(Alerta.estudiante_id == estudiante_id)
    if mias:
        consulta = consulta.where(Alerta.asignado_a == usuario.id)
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    items = list(db.scalars(consulta.order_by(Alerta.creado_en.desc(), Alerta.id.desc())
                            .offset((pagina - 1) * por_pagina).limit(por_pagina)).unique())
    return total, items


def obtener(db: Session, alerta_id: int, usuario: Usuario) -> Alerta:
    alerta = db.get(Alerta, alerta_id)
    if not alerta:
        raise NoEncontrado("Alerta no encontrada")
    visibles = programas_visibles(usuario)
    if visibles is not None and alerta.estudiante.programa_id not in visibles:
        raise SinPermiso("No tiene acceso a esta alerta")
    return alerta


def crear_manual(db: Session, datos: AlertaCrear) -> Alerta:
    if not db.get(Estudiante, datos.estudiante_id):
        raise NoEncontrado("Estudiante no encontrado")
    _validar_usuario(db, datos.asignado_a)
    alerta = Alerta(tipo="manual", **datos.model_dump())
    db.add(alerta)
    db.flush()
    return alerta


def actualizar(db: Session, alerta: Alerta, datos: AlertaActualizar) -> Alerta:
    cambios = datos.model_dump(exclude_unset=True)
    if "asignado_a" in cambios:
        _validar_usuario(db, cambios["asignado_a"])
        if alerta.estado == "pendiente" and cambios["asignado_a"] and "estado" not in cambios:
            alerta.estado = "en_proceso"
    for campo, valor in cambios.items():
        setattr(alerta, campo, valor)
    if alerta.estado in ("atendida", "cerrada") and not alerta.cerrado_en:
        alerta.cerrado_en = datetime.now()
    elif alerta.estado in ABIERTAS:
        alerta.cerrado_en = None
    db.flush()
    return alerta


def _validar_usuario(db: Session, usuario_id: int | None) -> None:
    if usuario_id is not None:
        u = db.get(Usuario, usuario_id)
        if not u or not u.activo:
            raise ErrorNegocio("El responsable indicado no existe o está inactivo")
