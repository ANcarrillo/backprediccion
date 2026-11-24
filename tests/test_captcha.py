"""Pruebas del CAPTCHA del inicio de sesión."""
import pytest

from app.core import captcha
from app.core.config import get_settings


@pytest.fixture()
def con_captcha(client, monkeypatch):
    ajustes = get_settings()
    ajustes.CAPTCHA_HABILITADO = True
    monkeypatch.setattr(captcha, "generar_texto", lambda longitud=None: "AB3CD")
    yield client
    ajustes.CAPTCHA_HABILITADO = False


def _login(client, token, respuesta):
    return client.post("/auth/login", data={"username": "admin@u.edu.co", "password": "Clave12345",
                                             "captcha_token": token or "", "captcha_respuesta": respuesta or ""})


def test_captcha_genera_imagen(admin, con_captcha):
    r = con_captcha.get("/auth/captcha").json()
    assert r["habilitado"] is True
    assert r["imagen"].startswith("data:image/png;base64,")
    assert "AB3CD" not in r["captcha_token"]


def test_login_sin_captcha_rechazado(admin, con_captcha):
    assert _login(con_captcha, None, None).status_code == 400


def test_login_captcha_incorrecto(admin, con_captcha):
    token = con_captcha.get("/auth/captcha").json()["captcha_token"]
    r = _login(con_captcha, token, "ZZZZZ")
    assert r.status_code == 400
    assert r.json()["detail"] == "CAPTCHA incorrecto o vencido"


def test_login_captcha_correcto_y_un_solo_uso(admin, con_captcha):
    token = con_captcha.get("/auth/captcha").json()["captcha_token"]
    assert _login(con_captcha, token, "ab3cd").status_code == 200  # no distingue mayúsculas
    assert _login(con_captcha, token, "AB3CD").status_code == 400  # ya fue usado


def test_captcha_deshabilitado(client):
    assert client.get("/auth/captcha").json() == {"habilitado": False}
