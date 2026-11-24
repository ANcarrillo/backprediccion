"""Catálogos: facultades, programas y periodos académicos."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, TODOS, requiere_roles
from app.data.database import get_db
from app.data.models import Facultad, PeriodoAcademico, Programa, Usuario
from app.schemas import FacultadIn, FacultadOut, PeriodoIn, PeriodoOut, ProgramaIn, ProgramaOut

router = APIRouter(prefix="/catalogos", tags=["Catálogos"])
lectura = requiere_roles(*TODOS)
escritura = requiere_roles(ADMIN)


def _guardar(db: Session, obj):
    try:
        db.add(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Registro duplicado o referencia inválida")
    db.refresh(obj)
    return obj


@router.get("/facultades", response_model=list[FacultadOut])
def facultades(db: Session = Depends(get_db), _: Usuario = Depends(lectura)):
    return list(db.scalars(select(Facultad).order_by(Facultad.nombre)))


@router.post("/facultades", response_model=FacultadOut, status_code=201)
def crear_facultad(datos: FacultadIn, db: Session = Depends(get_db), _: Usuario = Depends(escritura)):
    return _guardar(db, Facultad(**datos.model_dump()))


@router.get("/programas", response_model=list[ProgramaOut])
def programas(db: Session = Depends(get_db), _: Usuario = Depends(lectura)):
    return list(db.scalars(select(Programa).order_by(Programa.nombre)).unique())


@router.post("/programas", response_model=ProgramaOut, status_code=201)
def crear_programa(datos: ProgramaIn, db: Session = Depends(get_db), _: Usuario = Depends(escritura)):
    if not db.get(Facultad, datos.facultad_id):
        raise HTTPException(400, "La facultad no existe")
    return _guardar(db, Programa(**datos.model_dump()))


@router.put("/programas/{programa_id}", response_model=ProgramaOut)
def editar_programa(programa_id: int, datos: ProgramaIn, db: Session = Depends(get_db),
                    _: Usuario = Depends(escritura)):
    programa = db.get(Programa, programa_id)
    if not programa:
        raise HTTPException(404, "Programa no encontrado")
    for k, v in datos.model_dump().items():
        setattr(programa, k, v)
    return _guardar(db, programa)


@router.get("/periodos", response_model=list[PeriodoOut])
def periodos(db: Session = Depends(get_db), _: Usuario = Depends(lectura)):
    return list(db.scalars(select(PeriodoAcademico).order_by(PeriodoAcademico.fecha_inicio.desc())))


@router.post("/periodos", response_model=PeriodoOut, status_code=201)
def crear_periodo(datos: PeriodoIn, db: Session = Depends(get_db), _: Usuario = Depends(escritura)):
    if datos.actual:
        db.execute(update(PeriodoAcademico).values(actual=False))
    return _guardar(db, PeriodoAcademico(**datos.model_dump()))
