"""Crea el primer usuario administrador.

Uso:  python crear_admin.py --email admin@universidad.edu.co --nombres Admin --apellidos Sistema
      (la contraseña se pide por consola)
"""
import argparse
import getpass

from sqlalchemy import select

from app.data.database import SessionLocal
from app.data.models import Usuario
from app.schemas import UsuarioCrear
from app.services import usuarios


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--nombres", default="Administrador")
    p.add_argument("--apellidos", default="Sistema")
    p.add_argument("--password", help="Si no se indica, se pide por consola")
    a = p.parse_args()
    password = a.password or getpass.getpass("Contraseña (mínimo 8 caracteres): ")

    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(Usuario.email == a.email.lower())):
            print("Ya existe un usuario con ese correo.")
            return
        u = usuarios.crear(db, UsuarioCrear(nombres=a.nombres, apellidos=a.apellidos, email=a.email,
                                            password=password, rol="administrador"))
        db.commit()
        print(f"Administrador creado (id={u.id}, email={u.email})")


if __name__ == "__main__":
    main()
