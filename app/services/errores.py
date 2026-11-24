"""Errores de negocio. Los routers los convierten en respuestas HTTP (ver app/main.py)."""


class ErrorNegocio(Exception):
    status_code = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontrado(ErrorNegocio):
    status_code = 404


class Conflicto(ErrorNegocio):
    status_code = 409


class SinPermiso(ErrorNegocio):
    status_code = 403
