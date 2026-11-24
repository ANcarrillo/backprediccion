"""Capa 4 - Modelos ORM. Reflejan exactamente las tablas de database/schema.sql."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON, BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric,
    SmallInteger, String, Table, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")
Decimal = lambda p, s: Numeric(p, s, asdecimal=False)  # noqa: E731  (devuelve float)

usuario_programa = Table(
    "usuario_programa", Base.metadata,
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("programa_id", ForeignKey("programas.id", ondelete="CASCADE"), primary_key=True),
)


class Rol(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(200))


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    rol: Mapped[Rol] = relationship(lazy="joined")
    programas: Mapped[list["Programa"]] = relationship(secondary=usuario_programa)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"


class Facultad(Base):
    __tablename__ = "facultades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), unique=True)


class Programa(Base):
    __tablename__ = "programas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facultad_id: Mapped[int] = mapped_column(ForeignKey("facultades.id"))
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    nivel: Mapped[str] = mapped_column(String(30), default="pregrado")
    duracion_semestres: Mapped[int] = mapped_column(SmallInteger, default=10)

    facultad: Mapped[Facultad] = relationship(lazy="joined")


class PeriodoAcademico(Base):
    __tablename__ = "periodos_academicos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    actual: Mapped[bool] = mapped_column(Boolean, default=False)


class Estudiante(Base):
    __tablename__ = "estudiantes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    tipo_documento: Mapped[str] = mapped_column(String(5), default="CC")
    numero_documento: Mapped[str] = mapped_column(String(20), unique=True)
    nombres: Mapped[str] = mapped_column(String(100))
    apellidos: Mapped[str] = mapped_column(String(100))
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)
    genero: Mapped[str | None] = mapped_column(String(15))
    email: Mapped[str | None] = mapped_column(String(150))
    telefono: Mapped[str | None] = mapped_column(String(20))
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"))
    periodo_ingreso_id: Mapped[int | None] = mapped_column(ForeignKey("periodos_academicos.id"))
    semestre_actual: Mapped[int] = mapped_column(SmallInteger, default=1)
    puntaje_saber11: Mapped[int | None] = mapped_column(SmallInteger)
    tipo_colegio: Mapped[str | None] = mapped_column(String(10))
    estado: Mapped[str] = mapped_column(String(15), default="activo")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    programa: Mapped[Programa] = relationship(lazy="joined")
    periodo_ingreso: Mapped[PeriodoAcademico | None] = relationship()
    datos_academicos: Mapped[list["DatoAcademico"]] = relationship(back_populates="estudiante", cascade="all, delete-orphan")
    datos_socioeconomicos: Mapped[list["DatoSocioeconomico"]] = relationship(back_populates="estudiante", cascade="all, delete-orphan")


class DatoSocioeconomico(Base):
    __tablename__ = "datos_socioeconomicos"
    __table_args__ = (UniqueConstraint("estudiante_id", "periodo_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id", ondelete="CASCADE"))
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"))
    estrato: Mapped[int | None] = mapped_column(SmallInteger)
    ingreso_familiar: Mapped[float | None] = mapped_column(Decimal(12, 2))
    trabaja: Mapped[bool] = mapped_column(Boolean, default=False)
    horas_trabajo_semana: Mapped[int] = mapped_column(SmallInteger, default=0)
    personas_a_cargo: Mapped[int] = mapped_column(SmallInteger, default=0)
    tipo_vivienda: Mapped[str | None] = mapped_column(String(15))
    zona_residencia: Mapped[str | None] = mapped_column(String(10))
    distancia_km: Mapped[float | None] = mapped_column(Decimal(6, 2))
    tiene_beca: Mapped[bool] = mapped_column(Boolean, default=False)
    apoyo_financiero: Mapped[bool] = mapped_column(Boolean, default=False)
    nivel_educativo_padres: Mapped[str | None] = mapped_column(String(20))
    victima_conflicto: Mapped[bool] = mapped_column(Boolean, default=False)
    pertenece_etnia: Mapped[bool] = mapped_column(Boolean, default=False)
    discapacidad: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    estudiante: Mapped[Estudiante] = relationship(back_populates="datos_socioeconomicos")
    periodo: Mapped[PeriodoAcademico] = relationship(lazy="joined")


class Asignatura(Base):
    __tablename__ = "asignaturas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"))
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    creditos: Mapped[int] = mapped_column(SmallInteger)
    semestre: Mapped[int | None] = mapped_column(SmallInteger)


class DatoAcademico(Base):
    __tablename__ = "datos_academicos"
    __table_args__ = (UniqueConstraint("estudiante_id", "periodo_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id", ondelete="CASCADE"))
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"))
    semestre_cursado: Mapped[int] = mapped_column(SmallInteger)
    creditos_inscritos: Mapped[int] = mapped_column(SmallInteger, default=0)
    creditos_aprobados: Mapped[int] = mapped_column(SmallInteger, default=0)
    creditos_reprobados: Mapped[int] = mapped_column(SmallInteger, default=0)
    promedio_periodo: Mapped[float | None] = mapped_column(Decimal(3, 2))
    promedio_acumulado: Mapped[float | None] = mapped_column(Decimal(3, 2))
    asistencia_pct: Mapped[float | None] = mapped_column(Decimal(5, 2))
    materias_reprobadas: Mapped[int] = mapped_column(SmallInteger, default=0)
    materias_canceladas: Mapped[int] = mapped_column(SmallInteger, default=0)
    materias_repetidas: Mapped[int] = mapped_column(SmallInteger, default=0)
    estado_matricula: Mapped[str] = mapped_column(String(15), default="matriculado")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    estudiante: Mapped[Estudiante] = relationship(back_populates="datos_academicos")
    periodo: Mapped[PeriodoAcademico] = relationship(lazy="joined")


class Calificacion(Base):
    __tablename__ = "calificaciones"
    __table_args__ = (UniqueConstraint("estudiante_id", "asignatura_id", "periodo_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id", ondelete="CASCADE"))
    asignatura_id: Mapped[int] = mapped_column(ForeignKey("asignaturas.id"))
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"))
    nota_final: Mapped[float | None] = mapped_column(Decimal(3, 2))
    asistencia_pct: Mapped[float | None] = mapped_column(Decimal(5, 2))
    aprobada: Mapped[bool | None] = mapped_column(Boolean)
    intento: Mapped[int] = mapped_column(SmallInteger, default=1)


class ModeloML(Base):
    __tablename__ = "modelos_ml"
    __table_args__ = (UniqueConstraint("nombre", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    algoritmo: Mapped[str] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(20))
    ruta_archivo: Mapped[str] = mapped_column(String(255))
    metricas: Mapped[dict | None] = mapped_column(JSONType)
    hiperparametros: Mapped[dict | None] = mapped_column(JSONType)
    variables: Mapped[dict | None] = mapped_column(JSONType)
    fecha_entrenamiento: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    activo: Mapped[bool] = mapped_column(Boolean, default=False)
    registrado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))


class Prediccion(Base):
    __tablename__ = "predicciones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id", ondelete="CASCADE"))
    periodo_id: Mapped[int | None] = mapped_column(ForeignKey("periodos_academicos.id"))
    modelo_id: Mapped[int | None] = mapped_column(ForeignKey("modelos_ml.id"))
    probabilidad: Mapped[float] = mapped_column(Decimal(5, 4))
    nivel_riesgo: Mapped[str] = mapped_column(String(10))
    factores: Mapped[list | None] = mapped_column(JSONType)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    estudiante: Mapped[Estudiante] = relationship()
    periodo: Mapped[PeriodoAcademico | None] = relationship(lazy="joined")
    modelo: Mapped[ModeloML | None] = relationship(lazy="joined")


class Alerta(Base):
    __tablename__ = "alertas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id", ondelete="CASCADE"))
    prediccion_id: Mapped[int | None] = mapped_column(ForeignKey("predicciones.id", ondelete="SET NULL"))
    tipo: Mapped[str] = mapped_column(String(20))
    nivel: Mapped[str] = mapped_column(String(10))
    titulo: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(15), default="pendiente")
    asignado_a: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime)

    estudiante: Mapped[Estudiante] = relationship(lazy="joined")
    responsable: Mapped[Usuario | None] = relationship(lazy="joined")


class Intervencion(Base):
    __tablename__ = "intervenciones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("estudiantes.id", ondelete="CASCADE"))
    alerta_id: Mapped[int | None] = mapped_column(ForeignKey("alertas.id", ondelete="SET NULL"))
    responsable_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(Text)
    fecha: Mapped[date] = mapped_column(Date, default=date.today)
    resultado: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(15), default="programada")
    proxima_fecha: Mapped[date | None] = mapped_column(Date)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    estudiante: Mapped[Estudiante] = relationship(lazy="joined")
    responsable: Mapped[Usuario] = relationship(lazy="joined")


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    accion: Mapped[str] = mapped_column(String(50))
    entidad: Mapped[str | None] = mapped_column(String(50))
    entidad_id: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[dict | None] = mapped_column(JSONType)
    ip: Mapped[str | None] = mapped_column(String(45))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
