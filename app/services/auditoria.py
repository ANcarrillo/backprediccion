from sqlalchemy.orm import Session

from app.data.models import Auditoria


def registrar(db: Session, usuario_id: int | None, accion: str, entidad: str | None = None,
              entidad_id: int | None = None, detalle: dict | None = None, ip: str | None = None) -> None:
    db.add(Auditoria(usuario_id=usuario_id, accion=accion, entidad=entidad,
                     entidad_id=entidad_id, detalle=detalle, ip=ip))
