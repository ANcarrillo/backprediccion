# Backend — API REST con FastAPI

Capas 2, 3 y 4 de la arquitectura:

```
app/
├── main.py              Arranque de la API, CORS y manejo de errores
├── schemas.py           Capa 2 · Validación de datos (Pydantic) y respuestas JSON
├── api/
│   ├── deps.py          Capa 2 · Autenticación JWT y autorización por rol
│   └── routers/         Capa 2 · Endpoints REST
│       auth · usuarios · catalogos · estudiantes · datos_academicos
│       predicciones · alertas · intervenciones · reportes · modelo
├── services/            Capa 3 · Lógica de negocio
│   estudiantes   Gestión de estudiantes (crear, consultar, actualizar)
│   datos         Procesamiento de datos (registro, limpieza, carga CSV)
│   prediccion    Predicción de riesgo (cargar modelo, predecir, clasificar)
│   alertas       Gestión de alertas + reglas de riesgo
│   reportes      Reportes e indicadores (estadísticas, seguimiento, exportar)
├── data/                Capa 4 · Acceso a datos e inteligencia
│   database.py   Conexión PostgreSQL (SQLAlchemy)
│   models.py     Tablas (igual que database/schema.sql)
│   ml_engine.py  Carga del modelo .pkl y explicabilidad
└── core/                Configuración (.env) y seguridad (bcrypt + JWT)
```

## Instalación

```bash
py -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

Copie `.env.example` como `.env` y ajuste `DATABASE_URL` (contraseña de PostgreSQL) y `SECRET_KEY`.

## Crear el primer administrador

La base debe existir (ver `database/README.md`).

```bash
python crear_admin.py --email admin@universidad.edu.co --nombres Admin --apellidos Sistema
```

## Ejecutar

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentación Swagger / OpenAPI (Fase 6.3): http://localhost:8000/docs — use el botón **Authorize** con su correo y contraseña. El botón Authorize no envía el CAPTCHA: para usarlo ponga `CAPTCHA_HABILITADO=false` en `.env` y reinicie la API.
- Estado: http://localhost:8000/salud

## Endpoints principales

| Ruta | Descripción | Roles |
|---|---|---|
| `GET /auth/captcha` | Imagen CAPTCHA + token para el inicio de sesión | todos |
| `POST /auth/login` | Inicio de sesión (devuelve token JWT); requiere `captcha_token` y `captcha_respuesta` | todos |
| `GET /auth/me` | Usuario actual | todos |
| `/usuarios` | Crear, listar, editar usuarios | administrador |
| `/catalogos/facultades`, `/programas`, `/periodos` | Catálogos | lectura: todos · escritura: administrador |
| `/estudiantes` | Buscar, crear, actualizar; `/{id}/ficha` = todo el historial | crear/editar: admin, coordinador |
| `/datos-academicos` | Resumen académico por periodo (+ reglas de riesgo) | admin, coordinador |
| `/datos-academicos/socioeconomicos` | Datos socioeconómicos por periodo | admin, coordinador, bienestar |
| `POST /datos-academicos/importar?tipo=` | Carga masiva CSV | admin, coordinador |
| `POST /predicciones/estudiante/{id}` | Predecir un estudiante (con factores influyentes) | todos |
| `POST /predicciones/lote` | Predecir todos / un programa | admin, coordinador, bienestar |
| `/alertas` | Listar, crear manual, asignar responsable, cambiar estado | gestionar: admin, coordinador, bienestar |
| `/intervenciones` | Registrar y hacer seguimiento | todos |
| `/reportes/resumen`, `/riesgo-por-programa`, `/riesgo-por-semestre`, `/evolucion`, `/exportar` | Indicadores y exportación CSV | todos |
| `/modelo/disponibles`, `/registrar`, `/{id}/activar`, `/activo` | Gestión del modelo ML | admin (ver: todos) |

Coordinadores y docentes con programas asignados solo ven los estudiantes de esos programas.

## Reglas de negocio (configurables en `.env`)

- Probabilidad ≥ `UMBRAL_RIESGO_ALTO` (0.70) → riesgo **alto**; ≥ `UMBRAL_RIESGO_MEDIO` (0.40) → **medio**; si no, **bajo**.
- Riesgo alto (y medio si `ALERTA_RIESGO_MEDIO=true`) → alerta tipo *prediccion_ml*.
- Al guardar datos académicos: promedio < 3.0, ≥ 3 materias reprobadas o asistencia < 75 % → alertas *académica* / *asistencia*.
- Al guardar datos socioeconómicos: trabaja ≥ 30 h/semana, o estrato 0-1 sin beca ni apoyo → alerta *socioeconómica*.
- No se duplican alertas: si ya hay una abierta del mismo tipo, se actualiza.

## Explicabilidad

Cada predicción guarda en `predicciones.factores` las variables que más **aumentan** el riesgo de ese estudiante: se mide cuánto baja la probabilidad si esa variable tomara el valor típico (mediana/moda) de los datos de entrenamiento.

## Pruebas (Fase 5.1)

Usan SQLite en memoria y un modelo pequeño, no necesitan PostgreSQL:

```bash
pytest
```

Para pruebas con Postman (Fase 5.5) importe el esquema OpenAPI desde http://localhost:8000/openapi.json.
