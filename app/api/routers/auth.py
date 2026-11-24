from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core import captcha
from app.core.config import get_settings
from app.core.security import crear_token
from app.data.database import get_db
from app.data.models import Usuario
from app.schemas import Token, UsuarioOut
from app.services import auditoria, usuarios

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.get("/captcha", summary="Nuevo CAPTCHA para el inicio de sesión")
def nuevo_captcha():
    if not get_settings().CAPTCHA_HABILITADO:
        return {"habilitado": False}
    return {"habilitado": True, **captcha.crear()}


@router.post("/login", response_model=Token, summary="Iniciar sesión (username = correo)")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    captcha_token: str | None = Form(None, description="Token devuelto por GET /auth/captcha"),
    captcha_respuesta: str | None = Form(None, description="Caracteres que el usuario lee en la imagen"),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    if get_settings().CAPTCHA_HABILITADO and not captcha.verificar(captcha_token, captcha_respuesta):
        auditoria.registrar(db, None, "captcha_fallido", detalle={"email": form.username}, ip=ip)
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CAPTCHA incorrecto o vencido")
    usuario = usuarios.autenticar(db, form.username, form.password)
    if not usuario:
        auditoria.registrar(db, None, "login_fallido", detalle={"email": form.username}, ip=ip)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    auditoria.registrar(db, usuario.id, "login", "usuarios", usuario.id, ip=ip)
    db.commit()
    return Token(access_token=crear_token(usuario.id, usuario.rol.nombre), usuario=UsuarioOut.model_validate(usuario))


@router.get("/me", response_model=UsuarioOut, summary="Usuario autenticado")
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario
