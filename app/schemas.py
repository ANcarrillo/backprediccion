"""Capa 2 - Validación de datos de entrada y formato de las respuestas JSON (Pydantic)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

NivelRiesgo = Literal["bajo", "medio", "alto"]
EstadoEstudiante = Literal["activo", "desertor", "graduado", "retirado", "inactivo"]
EstadoAlerta = Literal["pendiente", "en_proceso", "atendida", "cerrada"]
TipoAlerta = Literal["prediccion_ml", "academica", "asistencia", "socioeconomica", "manual"]
TipoIntervencion = Literal["tutoria", "psicologica", "financiera", "academica", "familiar", "seguimiento", "otra"]
EstadoIntervencion = Literal["programada", "realizada", "cancelada"]
NombreRol = Literal["administrador", "coordinador", "docente", "bienestar"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- Autenticación y usuarios ----------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: "UsuarioOut"


class RolOut(ORM):
    id: int
    nombre: str
    descripcion: str | None = None


class UsuarioBase(BaseModel):
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    email: EmailStr
    rol: NombreRol
    programas_ids: list[int] = []


class UsuarioCrear(UsuarioBase):
    password: str = Field(min_length=8, max_length=72)


class UsuarioActualizar(BaseModel):
    nombres: str | None = Field(None, min_length=2, max_length=100)
    apellidos: str | None = Field(None, min_length=2, max_length=100)
    rol: NombreRol | None = None
    activo: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=72)
    programas_ids: list[int] | None = None


class ProgramaMini(ORM):
    id: int
    codigo: str
    nombre: str


class UsuarioOut(ORM):
    id: int
    nombres: str
    apellidos: str
    email: str
    activo: bool
    rol: RolOut
    programas: list[ProgramaMini] = []
    ultimo_acceso: datetime | None = None


class UsuarioMini(ORM):
    id: int
    nombres: str
    apellidos: str


# ---------------- Catálogos ----------------
class FacultadIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)


class FacultadOut(ORM):
    id: int
    nombre: str


class ProgramaIn(BaseModel):
    facultad_id: int
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=150)
    nivel: Literal["tecnico", "tecnologico", "pregrado", "especializacion", "maestria"] = "pregrado"
    duracion_semestres: int = Field(10, ge=1, le=14)


class ProgramaOut(ORM):
    id: int
    facultad_id: int
    codigo: str
    nombre: str
    nivel: str
    duracion_semestres: int
    facultad: FacultadOut


class PeriodoIn(BaseModel):
    codigo: str = Field(pattern=r"^\d{4}-[12]$", description="Formato AAAA-1 o AAAA-2")
    fecha_inicio: date
    fecha_fin: date
    actual: bool = False

    @model_validator(mode="after")
    def fechas(self):
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self


class PeriodoOut(ORM):
    id: int
    codigo: str
    fecha_inicio: date
    fecha_fin: date
    actual: bool


# ---------------- Estudiantes ----------------
class EstudianteBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    tipo_documento: Literal["CC", "TI", "CE", "PA", "PPT"] = "CC"
    numero_documento: str = Field(min_length=3, max_length=20)
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    fecha_nacimiento: date | None = None
    genero: Literal["masculino", "femenino", "otro"] | None = None
    email: EmailStr | None = None
    telefono: str | None = Field(None, max_length=20)
    programa_id: int
    periodo_ingreso_id: int | None = None
    semestre_actual: int = Field(1, ge=1, le=14)
    puntaje_saber11: int | None = Field(None, ge=0, le=500)
    tipo_colegio: Literal["publico", "privado"] | None = None
    estado: EstadoEstudiante = "activo"


class EstudianteCrear(EstudianteBase):
    pass


class EstudianteActualizar(BaseModel):
    tipo_documento: Literal["CC", "TI", "CE", "PA", "PPT"] | None = None
    numero_documento: str | None = Field(None, min_length=3, max_length=20)
    nombres: str | None = Field(None, min_length=2, max_length=100)
    apellidos: str | None = Field(None, min_length=2, max_length=100)
    fecha_nacimiento: date | None = None
    genero: Literal["masculino", "femenino", "otro"] | None = None
    email: EmailStr | None = None
    telefono: str | None = Field(None, max_length=20)
    programa_id: int | None = None
    periodo_ingreso_id: int | None = None
    semestre_actual: int | None = Field(None, ge=1, le=14)
    puntaje_saber11: int | None = Field(None, ge=0, le=500)
    tipo_colegio: Literal["publico", "privado"] | None = None
    estado: EstadoEstudiante | None = None


class RiesgoResumen(BaseModel):
    probabilidad: float
    nivel_riesgo: NivelRiesgo
    fecha: datetime


class EstudianteOut(ORM):
    id: int
    codigo: str
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str
    fecha_nacimiento: date | None
    genero: str | None
    email: str | None
    telefono: str | None
    programa_id: int
    programa: ProgramaMini
    periodo_ingreso_id: int | None
    semestre_actual: int
    puntaje_saber11: int | None
    tipo_colegio: str | None
    estado: str
    riesgo: RiesgoResumen | None = None


class Pagina(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list


class PaginaEstudiantes(Pagina):
    items: list[EstudianteOut]


# ---------------- Datos académicos y socioeconómicos ----------------
class DatoAcademicoIn(BaseModel):
    estudiante_id: int
    periodo_id: int
    semestre_cursado: int = Field(ge=1, le=14)
    creditos_inscritos: int = Field(0, ge=0)
    creditos_aprobados: int = Field(0, ge=0)
    creditos_reprobados: int = Field(0, ge=0)
    promedio_periodo: float | None = Field(None, ge=0, le=5)
    promedio_acumulado: float | None = Field(None, ge=0, le=5)
    asistencia_pct: float | None = Field(None, ge=0, le=100)
    materias_reprobadas: int = Field(0, ge=0)
    materias_canceladas: int = Field(0, ge=0)
    materias_repetidas: int = Field(0, ge=0)
    estado_matricula: Literal["matriculado", "cancelado", "aplazado", "no_matriculado"] = "matriculado"

    @model_validator(mode="after")
    def creditos(self):
        if self.creditos_aprobados + self.creditos_reprobados > self.creditos_inscritos:
            raise ValueError("Créditos aprobados + reprobados no pueden superar los inscritos")
        return self


class DatoAcademicoOut(ORM):
    id: int
    estudiante_id: int
    periodo_id: int
    periodo: PeriodoOut
    semestre_cursado: int
    creditos_inscritos: int
    creditos_aprobados: int
    creditos_reprobados: int
    promedio_periodo: float | None
    promedio_acumulado: float | None
    asistencia_pct: float | None
    materias_reprobadas: int
    materias_canceladas: int
    materias_repetidas: int
    estado_matricula: str


class DatoSocioIn(BaseModel):
    estudiante_id: int
    periodo_id: int
    estrato: int | None = Field(None, ge=0, le=6)
    ingreso_familiar: float | None = Field(None, ge=0)
    trabaja: bool = False
    horas_trabajo_semana: int = Field(0, ge=0, le=80)
    personas_a_cargo: int = Field(0, ge=0)
    tipo_vivienda: Literal["propia", "arriendo", "familiar", "residencia", "otra"] | None = None
    zona_residencia: Literal["urbana", "rural"] | None = None
    distancia_km: float | None = Field(None, ge=0)
    tiene_beca: bool = False
    apoyo_financiero: bool = False
    nivel_educativo_padres: Literal["ninguno", "primaria", "secundaria", "tecnico", "universitario", "posgrado"] | None = None
    victima_conflicto: bool = False
    pertenece_etnia: bool = False
    discapacidad: bool = False


class DatoSocioOut(ORM, DatoSocioIn):
    id: int
    periodo: PeriodoOut


class ResultadoImportacion(BaseModel):
    insertados: int
    actualizados: int
    errores: list[str]
    alertas_generadas: int = 0


# ---------------- Predicciones ----------------
class Factor(BaseModel):
    variable: str
    valor: float | str | None = None
    referencia: float | str | None = None
    impacto: float


class PrediccionOut(ORM):
    id: int
    estudiante_id: int
    periodo_id: int | None
    modelo_id: int | None
    probabilidad: float
    nivel_riesgo: NivelRiesgo
    factores: list[Factor] | None
    creado_en: datetime


class PrediccionLoteIn(BaseModel):
    programa_id: int | None = None
    solo_activos: bool = True


class PrediccionLoteOut(BaseModel):
    procesados: int
    sin_datos: int
    por_nivel: dict[str, int]
    alertas_generadas: int


# ---------------- Alertas ----------------
class EstudianteMini(ORM):
    id: int
    codigo: str
    nombres: str
    apellidos: str
    programa: ProgramaMini


class AlertaCrear(BaseModel):
    estudiante_id: int
    nivel: NivelRiesgo = "medio"
    titulo: str = Field(min_length=3, max_length=150)
    descripcion: str | None = None
    asignado_a: int | None = None


class AlertaActualizar(BaseModel):
    estado: EstadoAlerta | None = None
    asignado_a: int | None = None
    descripcion: str | None = None


class AlertaOut(ORM):
    id: int
    estudiante_id: int
    estudiante: EstudianteMini
    prediccion_id: int | None
    tipo: TipoAlerta
    nivel: NivelRiesgo
    titulo: str
    descripcion: str | None
    estado: EstadoAlerta
    asignado_a: int | None
    responsable: UsuarioMini | None
    creado_en: datetime
    cerrado_en: datetime | None


class PaginaAlertas(Pagina):
    items: list[AlertaOut]


# ---------------- Intervenciones ----------------
class IntervencionCrear(BaseModel):
    estudiante_id: int
    alerta_id: int | None = None
    responsable_id: int | None = None   # por defecto, el usuario que registra
    tipo: TipoIntervencion
    descripcion: str = Field(min_length=3)
    fecha: date | None = None
    resultado: str | None = None
    estado: EstadoIntervencion = "programada"
    proxima_fecha: date | None = None


class IntervencionActualizar(BaseModel):
    tipo: TipoIntervencion | None = None
    descripcion: str | None = None
    fecha: date | None = None
    resultado: str | None = None
    estado: EstadoIntervencion | None = None
    proxima_fecha: date | None = None


class IntervencionOut(ORM):
    id: int
    estudiante_id: int
    estudiante: EstudianteMini
    alerta_id: int | None
    responsable: UsuarioMini
    tipo: TipoIntervencion
    descripcion: str
    fecha: date
    resultado: str | None
    estado: EstadoIntervencion
    proxima_fecha: date | None
    creado_en: datetime


# ---------------- Ficha completa ----------------
class FichaEstudiante(BaseModel):
    estudiante: EstudianteOut
    academicos: list[DatoAcademicoOut]
    socioeconomicos: list[DatoSocioOut]
    predicciones: list[PrediccionOut]
    alertas: list[AlertaOut]
    intervenciones: list[IntervencionOut]


# ---------------- Modelo ML ----------------
class ModeloOut(ORM):
    id: int
    nombre: str
    algoritmo: str
    version: str
    ruta_archivo: str
    metricas: dict | None
    hiperparametros: dict | None
    variables: dict | None
    fecha_entrenamiento: datetime
    activo: bool


class ModeloRegistrar(BaseModel):
    archivo: str = Field(description="Nombre del .pkl dentro de MODELS_DIR")
    activar: bool = True


Token.model_rebuild()
