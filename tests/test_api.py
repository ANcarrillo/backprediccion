"""Pruebas de integración de la API (Fase 5.1)."""


def preparar_catalogos(client, h):
    fac = client.post("/catalogos/facultades", json={"nombre": "Ingeniería"}, headers=h).json()
    prog = client.post("/catalogos/programas", json={"facultad_id": fac["id"], "codigo": "ISIS",
                                                     "nombre": "Ingeniería de Sistemas"}, headers=h).json()
    per = client.post("/catalogos/periodos", json={"codigo": "2026-1", "fecha_inicio": "2026-02-01",
                                                   "fecha_fin": "2026-06-30", "actual": True}, headers=h).json()
    return prog, per


def crear_estudiante(client, h, prog, codigo="2026001", doc="100200300"):
    r = client.post("/estudiantes", json={"codigo": codigo, "numero_documento": doc, "nombres": "Laura",
                                          "apellidos": "Gómez", "programa_id": prog["id"],
                                          "fecha_nacimiento": "2005-04-10", "tipo_colegio": "publico"}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_login_incorrecto(client, admin):
    r = client.post("/auth/login", data={"username": "admin@u.edu.co", "password": "mala-clave"})
    assert r.status_code == 401


def test_sin_token(client):
    assert client.get("/estudiantes").status_code == 401


def test_flujo_completo(client, admin):
    h = admin
    prog, per = preparar_catalogos(client, h)
    est = crear_estudiante(client, h, prog)

    # Duplicado
    assert client.post("/estudiantes", json={"codigo": "2026001", "numero_documento": "999", "nombres": "Xx",
                                             "apellidos": "Yy", "programa_id": prog["id"]}, headers=h).status_code == 409

    # Validación: créditos inconsistentes
    malo = {"estudiante_id": est["id"], "periodo_id": per["id"], "semestre_cursado": 2,
            "creditos_inscritos": 10, "creditos_aprobados": 9, "creditos_reprobados": 5}
    assert client.post("/datos-academicos", json=malo, headers=h).status_code == 422

    # Datos académicos de riesgo -> reglas generan alertas
    acad = {"estudiante_id": est["id"], "periodo_id": per["id"], "semestre_cursado": 2,
            "creditos_inscritos": 18, "creditos_aprobados": 9, "creditos_reprobados": 9,
            "promedio_periodo": 2.4, "promedio_acumulado": 2.9, "asistencia_pct": 55,
            "materias_reprobadas": 3}
    r = client.post("/datos-academicos", json=acad, headers=h)
    assert r.status_code == 201, r.text
    r = client.post("/datos-academicos/socioeconomicos", json={
        "estudiante_id": est["id"], "periodo_id": per["id"], "estrato": 1, "trabaja": True,
        "horas_trabajo_semana": 35, "zona_residencia": "rural"}, headers=h)
    assert r.status_code == 201, r.text

    alertas = client.get("/alertas", params={"estudiante_id": est["id"]}, headers=h).json()
    tipos = {a["tipo"] for a in alertas["items"]}
    assert {"academica", "asistencia", "socioeconomica"} <= tipos

    # Sin modelo activo -> 409
    assert client.post(f"/predicciones/estudiante/{est['id']}", headers=h).status_code == 409

    # Registrar y activar el modelo
    disp = client.get("/modelo/disponibles", headers=h).json()
    assert disp[0]["archivo"] == "modelo_prueba.pkl"
    r = client.post("/modelo/registrar", json={"archivo": "modelo_prueba.pkl"}, headers=h)
    assert r.status_code == 201 and r.json()["activo"], r.text

    # Predicción individual con explicación
    r = client.post(f"/predicciones/estudiante/{est['id']}", headers=h)
    assert r.status_code == 201, r.text
    pred = r.json()
    assert pred["nivel_riesgo"] == "alto" and pred["probabilidad"] >= 0.7
    assert pred["factores"] and pred["factores"][0]["impacto"] > 0
    alertas = client.get("/alertas", params={"tipo": "prediccion_ml"}, headers=h).json()
    assert alertas["total"] == 1

    # Ficha completa
    ficha = client.get(f"/estudiantes/{est['id']}/ficha", headers=h).json()
    assert ficha["estudiante"]["riesgo"]["nivel_riesgo"] == "alto"
    assert len(ficha["academicos"]) == 1 and len(ficha["predicciones"]) == 1

    # Lote (un estudiante sin datos)
    crear_estudiante(client, h, prog, codigo="2026002", doc="555")
    lote = client.post("/predicciones/lote", json={}, headers=h).json()
    assert lote["procesados"] == 1 and lote["sin_datos"] == 1
    assert client.get("/alertas", params={"tipo": "prediccion_ml"}, headers=h).json()["total"] == 1  # sin duplicar

    # Gestión de alerta + intervención
    alerta_id = alertas["items"][0]["id"]
    yo = client.get("/auth/me", headers=h).json()
    r = client.put(f"/alertas/{alerta_id}", json={"asignado_a": yo["id"]}, headers=h)
    assert r.json()["estado"] == "en_proceso"
    r = client.post("/intervenciones", json={"estudiante_id": est["id"], "alerta_id": alerta_id,
                                             "tipo": "tutoria", "descripcion": "Tutoría de matemáticas"}, headers=h)
    assert r.status_code == 201, r.text
    r = client.put(f"/alertas/{alerta_id}", json={"estado": "atendida"}, headers=h)
    assert r.json()["cerrado_en"] is not None

    # Reportes
    res = client.get("/reportes/resumen", headers=h).json()
    assert res["total_estudiantes"] == 2 and res["por_nivel"]["alto"] == 1
    assert client.get("/reportes/riesgo-por-programa", headers=h).json()[0]["alto"] == 1
    assert len(client.get("/reportes/evolucion", headers=h).json()) == 1
    csv = client.get("/reportes/exportar", headers=h)
    assert csv.status_code == 200 and "2026001" in csv.text

    # Búsqueda y filtro por riesgo
    lista = client.get("/estudiantes", params={"nivel_riesgo": "alto"}, headers=h).json()
    assert lista["total"] == 1 and lista["items"][0]["codigo"] == "2026001"
    assert client.get("/estudiantes", params={"q": "gómez"}, headers=h).json()["total"] == 2


def test_permisos_por_rol(client, admin):
    h = admin
    prog, _ = preparar_catalogos(client, h)
    r = client.post("/usuarios", json={"nombres": "Diego", "apellidos": "Docente", "email": "doc@u.edu.co",
                                       "password": "Clave12345", "rol": "docente"}, headers=h)
    assert r.status_code == 201, r.text
    tok = client.post("/auth/login", data={"username": "doc@u.edu.co", "password": "Clave12345"}).json()
    hd = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.get("/estudiantes", headers=hd).status_code == 200
    assert client.post("/estudiantes", json={"codigo": "1", "numero_documento": "123", "nombres": "Aa",
                                             "apellidos": "Bb", "programa_id": prog["id"]}, headers=hd).status_code == 403
    assert client.get("/usuarios", headers=hd).status_code == 403


def test_importar_csv(client, admin):
    h = admin
    prog, per = preparar_catalogos(client, h)
    crear_estudiante(client, h, prog)
    csv = ("codigo_estudiante;periodo;semestre_cursado;creditos_inscritos;creditos_aprobados;promedio_periodo;asistencia_pct\n"
           "2026001;2026-1;3;18;18;4,2;95\n"
           "9999;2026-1;3;18;18;4.0;90\n"
           "2026001;2026-1;3;18;18;7.5;90\n")
    r = client.post("/datos-academicos/importar", params={"tipo": "academicos"},
                    files={"archivo": ("datos.csv", csv.encode("utf-8"), "text/csv")}, headers=h)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["insertados"] == 1 and len(res["errores"]) == 2
