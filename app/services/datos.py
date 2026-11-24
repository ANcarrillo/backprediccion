"""Capa 3 - Procesamiento de datos: registro, limpieza y transformación de los datos
académicos y socioeconómicos (manual o por archivo CSV)."""
import csv
import io

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import DatoAcademico, DatoSocioeconomico, Estudiante, PeriodoAcademico, Usuario
from app.schemas import DatoAcademicoIn, DatoSocioIn

from . import alertas as srv_alertas
from . import estudiantes as srv_estudiantes
from .errores import ErrorNegocio, NoEncontrado

VERDADERO = {"si", "sí", "s", "true", "1", "x", "yes"}
FALSO = {"no", "n", "false", "0", ""}


def _validar_periodo(db: Session, periodo_id: int) -> None:
    if not db.get(PeriodoAcademico, periodo_id):
        raise ErrorNegocio("El periodo académico no existe")


def guardar_academico(db: Session, datos: DatoAcademicoIn, usuario: Usuario) -> tuple[DatoAcademico, bool, int]:
    """Inserta o actualiza (estudiante, periodo). Devuelve (registro, es_nuevo, alertas_generadas)."""
    est = srv_estudiantes.obtener(db, datos.estudiante_id, usuario)
    _validar_periodo(db, datos.periodo_id)
    registro = db.scalar(select(DatoAcademico).where(DatoAcademico.estudiante_id == est.id,
                                                     DatoAcademico.periodo_id == datos.periodo_id))
    nuevo = registro is None
    if nuevo:
        registro = DatoAcademico(**datos.model_dump())
        db.add(registro)
    else:
        for campo, valor in datos.model_dump().items():
            setattr(registro, campo, valor)
    if datos.semestre_cursado > est.semestre_actual:
        est.semestre_actual = datos.semestre_cursado
    db.flush()
    return registro, nuevo, srv_alertas.reglas_academicas(db, registro)


def guardar_socioeconomico(db: Session, datos: DatoSocioIn, usuario: Usuario) -> tuple[DatoSocioeconomico, bool, int]:
    est = srv_estudiantes.obtener(db, datos.estudiante_id, usuario)
    _validar_periodo(db, datos.periodo_id)
    valores = datos.model_dump()
    if not valores["trabaja"]:
        valores["horas_trabajo_semana"] = 0
    registro = db.scalar(select(DatoSocioeconomico).where(DatoSocioeconomico.estudiante_id == est.id,
                                                          DatoSocioeconomico.periodo_id == datos.periodo_id))
    nuevo = registro is None
    if nuevo:
        registro = DatoSocioeconomico(**valores)
        db.add(registro)
    else:
        for campo, valor in valores.items():
            setattr(registro, campo, valor)
    db.flush()
    return registro, nuevo, srv_alertas.reglas_socioeconomicas(db, registro)


def eliminar(db: Session, modelo, registro_id: int, usuario: Usuario) -> None:
    registro = db.get(modelo, registro_id)
    if not registro:
        raise NoEncontrado("Registro no encontrado")
    srv_estudiantes.obtener(db, registro.estudiante_id, usuario)  # verifica acceso
    db.delete(registro)


# ---------------- Importación CSV ----------------
def _limpiar_valor(campo: str, valor: str | None, booleanos: set[str]):
    if valor is None:
        return None
    valor = valor.strip()
    if campo in booleanos:
        v = valor.lower()
        if v in VERDADERO:
            return True
        if v in FALSO:
            return False
        raise ValueError(f"valor booleano inválido en '{campo}': {valor}")
    if valor == "":
        return None
    if valor.replace(",", "").replace(".", "").replace("-", "").isdigit():
        return valor.replace(",", ".")   # decimales con coma
    return valor.lower()


def importar_csv(db: Session, contenido: bytes, tipo: str, usuario: Usuario) -> dict:
    """Columnas obligatorias: codigo_estudiante, periodo (ej. 2026-1) + campos del esquema."""
    esquema = {"academicos": DatoAcademicoIn, "socioeconomicos": DatoSocioIn}.get(tipo)
    if not esquema:
        raise ErrorNegocio("tipo debe ser 'academicos' o 'socioeconomicos'")
    guardar = guardar_academico if tipo == "academicos" else guardar_socioeconomico
    booleanos = {n for n, f in esquema.model_fields.items() if f.annotation is bool}

    texto = contenido.decode("utf-8-sig")
    separador = ";" if texto.splitlines()[0].count(";") > texto.splitlines()[0].count(",") else ","
    lector = csv.DictReader(io.StringIO(texto), delimiter=separador)
    lector.fieldnames = [c.strip().lower() for c in (lector.fieldnames or [])]
    faltan = {"codigo_estudiante", "periodo"} - set(lector.fieldnames)
    if faltan:
        raise ErrorNegocio(f"Faltan columnas obligatorias: {', '.join(sorted(faltan))}")

    estudiantes = {e.codigo: e.id for e in db.scalars(select(Estudiante))}
    periodos = {p.codigo: p.id for p in db.scalars(select(PeriodoAcademico))}
    resultado = {"insertados": 0, "actualizados": 0, "errores": [], "alertas_generadas": 0}

    for n, fila in enumerate(lector, start=2):
        try:
            codigo = (fila.pop("codigo_estudiante") or "").strip()
            periodo = (fila.pop("periodo") or "").strip()
            if codigo not in estudiantes:
                raise ValueError(f"estudiante '{codigo}' no existe")
            if periodo not in periodos:
                raise ValueError(f"periodo '{periodo}' no existe")
            valores = {k: _limpiar_valor(k, v, booleanos) for k, v in fila.items()
                       if k in esquema.model_fields}
            valores = {k: v for k, v in valores.items() if v is not None}
            datos = esquema(estudiante_id=estudiantes[codigo], periodo_id=periodos[periodo], **valores)
            with db.begin_nested():
                _, nuevo, alertas = guardar(db, datos, usuario)
            resultado["insertados" if nuevo else "actualizados"] += 1
            resultado["alertas_generadas"] += alertas
        except ValidationError as exc:
            detalle = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            resultado["errores"].append(f"Fila {n}: {detalle}")
        except (ValueError, ErrorNegocio) as exc:
            resultado["errores"].append(f"Fila {n}: {exc}")
    return resultado
