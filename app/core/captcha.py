"""CAPTCHA propio para el inicio de sesión (sin servicios externos).

1. GET /auth/captcha genera un texto aleatorio, lo dibuja distorsionado en una imagen PNG
   y devuelve la imagen + un token firmado (JWT) que contiene un HMAC de la respuesta.
2. POST /auth/login recibe el token y lo que escribió el usuario; se verifica el HMAC.

La respuesta nunca viaja en claro, el token vence a los pocos minutos y cada código
solo se puede usar una vez.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import math
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

import jwt
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import get_settings

# Sin caracteres que se confunden (0/O, 1/I/L)
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ANCHO, ALTO = 200, 70

_usados: dict[str, float] = {}  # nonce -> instante en que vence
_bloqueo = threading.Lock()


def generar_texto(longitud: int | None = None) -> str:
    return "".join(secrets.choice(ALFABETO) for _ in range(longitud or get_settings().CAPTCHA_LONGITUD))


def _firma(texto: str, nonce: str) -> str:
    clave = get_settings().SECRET_KEY.encode()
    return hmac.new(clave, f"captcha:{nonce}:{texto.strip().upper()}".encode(), hashlib.sha256).hexdigest()


def _fuente(tamano: int) -> ImageFont.ImageFont:
    for nombre in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nombre, tamano)
        except OSError:
            continue
    return ImageFont.load_default(size=tamano)


def dibujar(texto: str) -> bytes:
    """Imagen PNG con el texto rotado, desplazado y con ruido."""
    rnd = secrets.SystemRandom()
    img = Image.new("RGB", (ANCHO, ALTO), (rnd.randint(235, 255), rnd.randint(235, 255), rnd.randint(235, 255)))
    d = ImageDraw.Draw(img)

    # Ruido de fondo
    for _ in range(250):
        d.point((rnd.randrange(ANCHO), rnd.randrange(ALTO)), fill=tuple(rnd.randint(120, 220) for _ in range(3)))
    for _ in range(4):
        d.line([(rnd.randrange(ANCHO), rnd.randrange(ALTO)) for _ in range(2)],
               fill=tuple(rnd.randint(140, 200) for _ in range(3)), width=1)

    # Cada carácter en su propia capa, rotado y desplazado
    paso = (ANCHO - 20) / len(texto)
    for i, c in enumerate(texto):
        fuente = _fuente(rnd.randint(34, 42))
        capa = Image.new("RGBA", (60, 70), (0, 0, 0, 0))
        color = (rnd.randint(10, 90), rnd.randint(10, 90), rnd.randint(60, 140), 255)
        ImageDraw.Draw(capa).text((12, 6), c, font=fuente, fill=color)
        capa = capa.rotate(rnd.uniform(-28, 28), resample=Image.BICUBIC, expand=False)
        x = int(10 + i * paso + rnd.uniform(-4, 4))
        y = int(rnd.uniform(-6, 4))
        img.paste(capa, (x, y), capa)

    # Curva que cruza el texto
    fase, amplitud, y0 = rnd.uniform(0, math.pi), rnd.uniform(6, 12), rnd.uniform(28, 42)
    puntos = [(x, y0 + amplitud * math.sin(x / 22 + fase)) for x in range(0, ANCHO, 4)]
    d.line(puntos, fill=(60, 60, 110), width=2)

    img = img.filter(ImageFilter.SMOOTH)
    salida = io.BytesIO()
    img.save(salida, format="PNG")
    return salida.getvalue()


def crear() -> dict:
    """Devuelve {captcha_token, imagen (data URL)} para mostrar en el formulario."""
    s = get_settings()
    texto = generar_texto()
    nonce = secrets.token_urlsafe(16)
    vence = datetime.now(timezone.utc) + timedelta(seconds=s.CAPTCHA_VIGENCIA_SEGUNDOS)
    token = jwt.encode({"tipo": "captcha", "n": nonce, "h": _firma(texto, nonce), "exp": vence},
                       s.SECRET_KEY, algorithm=s.ALGORITMO_JWT)
    imagen = "data:image/png;base64," + base64.b64encode(dibujar(texto)).decode()
    return {"captcha_token": token, "imagen": imagen}


def _limpiar_usados(ahora: float) -> None:
    for n in [n for n, vence in _usados.items() if vence < ahora]:
        del _usados[n]


def verificar(token: str | None, respuesta: str | None) -> bool:
    """True si la respuesta coincide. El código queda usado (también si falla)."""
    if not token or not respuesta:
        return False
    s = get_settings()
    try:
        datos = jwt.decode(token, s.SECRET_KEY, algorithms=[s.ALGORITMO_JWT])
    except jwt.PyJWTError:
        return False
    if datos.get("tipo") != "captcha" or not datos.get("n") or not datos.get("h"):
        return False
    ahora = time.time()
    with _bloqueo:
        _limpiar_usados(ahora)
        if datos["n"] in _usados:
            return False
        _usados[datos["n"]] = float(datos["exp"])
    return hmac.compare_digest(datos["h"], _firma(respuesta, datos["n"]))
