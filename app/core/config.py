from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_BACKEND = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ_BACKEND / ".env", extra="ignore")

    APP_NOMBRE: str = "API - Alerta temprana de deserción"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/desercion_db"
    SECRET_KEY: str = "cambie-esta-clave-secreta"
    ALGORITMO_JWT: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    MODELS_DIR: str = "../ml/models"

    # CAPTCHA en el inicio de sesión
    CAPTCHA_HABILITADO: bool = True
    CAPTCHA_LONGITUD: int = 5
    CAPTCHA_VIGENCIA_SEGUNDOS: int = 300

    # Reglas de negocio (Capa 3)
    UMBRAL_RIESGO_MEDIO: float = 0.40
    UMBRAL_RIESGO_ALTO: float = 0.70
    ALERTA_RIESGO_MEDIO: bool = True
    REGLA_PROMEDIO_MINIMO: float = 3.0
    REGLA_ASISTENCIA_MINIMA: float = 75
    REGLA_MATERIAS_REPROBADAS: int = 3
    REGLA_HORAS_TRABAJO: int = 30

    @property
    def cors_lista(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def dir_modelos(self) -> Path:
        ruta = Path(self.MODELS_DIR)
        return ruta if ruta.is_absolute() else (RAIZ_BACKEND / ruta).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
