"""F2.3 + M12 fase 1: portal del cliente y conversaciones por expediente (T-31: portal propio, sin WhatsApp).

Todo con datos FICTICIOS. Comprueba acceso separado del cliente, permisos reales en el servidor, notas internas,
nada se borra, avisos sin contenido por correo, urgentes con fecha validada y escalado, adjuntos al expediente y
exportación con huella."""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from .conftest import CSRF
from .test_f41_extranjeria import _new_case

API = "/api/v1"
PDF = "application/pdf"


# ------------------------------------------------------------------ utilidades
def _with_email(db, case_id) -> tuple[uuid.UUID, str]:
    from app.models import CaseFile, ContactPoint

    cf = db.get(CaseFile, case_id)
    email = f"cliente.{uuid.uuid4().hex[:10]}@ejemplo.invalid"
    db.add(ContactPoint(contact_id=cf.contact_id, kind="email", value_normalized=email, is_primary=True))
    db.commit()
    return cf.contact_id, email


def _client(app) -> TestClient:
    c = TestClient(app)
    c.headers.update(CSRF)
    return c


def _portal_login(app, email: str, accept: bool = True) -> TestClient:
    c = _client(app)
    r = c.post(f"{API}/portal/auth/request-code", json={"email": email})
    code = r.json()["dev_code"]
    assert c.post(f"{API}/portal/auth/verify", json={"email": email, "code": code}).status_code == 200
    if accept:
        assert c.post(f"{API}/portal/terms", json={"accept": True}).status_code == 200
    return c


def _invited(app, login, db, procedure="ARR-SOCIOLABORAL", staff="asesor.extranjeria.mad"):
    cid = _new_case(db, procedure=procedure, given="Carla", family="Ferrer Demo")
    contact, email = _with_email(db, cid)
    s = login(staff)
    r = s.post(f"{API}/comm/contacts/{contact}/portal/invite", json={"email": email})
    assert r.status_code == 200, r.text
    return cid, contact, email, s


def _case_thread(s, cid):
    r = s.get(f"{API}/comm/cases/{cid}/thread")
    assert r.status_code == 200, r.text
    return r.json()


def _send(s, tid, **form):
    files = form.pop("files", None)
    return s.post(f"{API}/comm/threads/{tid}/messages", data={k: str(v) for k, v in form.items()}, files=files)


# ------------------------------------------------------------------ acceso del cliente
def test_invitacion_solo_con_correo_de_la_ficha_y_bienvenida(app, login, db):
    cid = _new_case(db, procedure="ARR-SOCIOLABORAL")
    contact, email = _with_email(db, cid)
    s = login("asesor.extranjeria.mad")
    bad = s.post(f"{API}/comm/contacts/{contact}/portal/invite", json={"email": "otro@ejemplo.invalid"})
    assert bad.status_code == 422 and "ficha" in bad.json()["error"]["message"]
    ok = s.post(f"{API}/comm/contacts/{contact}/portal/invite", json={"email": email.upper()})
    assert ok.status_code == 200 and ok.json()["status"] == "invitada"
    assert ok.json()["outbox"][0]["purpose"] == "invitacion"
    # Reinvitar no duplica el correo de invitación
    s.post(f"{API}/comm/contacts/{contact}/portal/invite", json={"email": email})
    assert db.execute(text("SELECT count(*) FROM comm_outbox WHERE purpose='invitacion' AND to_address=:e"),
                      {"e": email}).scalar_one() == 1
    general = s.get(f"{API}/comm/contacts/{contact}/thread").json()
    assert general["messages"][0]["kind"] == "sistema" and "bienvenida" in general["messages"][0]["text"]


def test_pedir_codigo_no_revela_quien_es_cliente(app, login, db):
    _cid, _contact, email, _s = _invited(app, login, db)
    c = _client(app)
    known = c.post(f"{API}/portal/auth/request-code", json={"email": email}).json()
    unknown = c.post(f"{API}/portal/auth/request-code", json={"email": "nadie@ejemplo.invalid"}).json()
    assert known["message"] == unknown["message"] and "dev_code" not in unknown
    # El código se guarda solo como hash
    assert not db.execute(text("SELECT count(*) FROM portal_code WHERE code_hash = :c"), {"c": known["dev_code"]}).scalar_one()


def test_codigo_incorrecto_caduca_tras_cinco_intentos(app, login, db):
    _cid, _contact, email, _s = _invited(app, login, db)
    c = _client(app)
    code = c.post(f"{API}/portal/auth/request-code", json={"email": email}).json()["dev_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert c.post(f"{API}/portal/auth/verify", json={"email": email, "code": wrong}).status_code in (401, 429)
    r = c.post(f"{API}/portal/auth/verify", json={"email": email, "code": code})
    assert r.status_code in (401, 429)  # el código quedó anulado (y el correo, bloqueado unos minutos)


def test_condiciones_obligatorias_y_sesiones_separadas(app, login, db):
    cid, _contact, email, staff = _invited(app, login, db)
    c = _portal_login(app, email, accept=False)
    assert c.get(f"{API}/portal/me").json()["needs_terms"] is True
    assert c.get(f"{API}/portal/threads").status_code == 403
    assert c.post(f"{API}/portal/terms", json={"accept": True}).status_code == 200
    assert db.execute(text("SELECT count(*) FROM consent c JOIN portal_account p ON p.consent_id = c.id "
                           "WHERE p.email = :e AND c.purpose='portal_comunicaciones'"), {"e": email}).scalar_one() == 1
    assert c.get(f"{API}/portal/threads").status_code == 200
    # La cookie del cliente no abre nada del equipo, ni la del equipo el portal
    assert c.get(f"{API}/comm/inbox").status_code == 401
    assert c.get(f"{API}/cases/{cid}").status_code == 401
    assert staff.get(f"{API}/portal/threads").status_code == 401


# ------------------------------------------------------------------ lo que ve el cliente
def test_cliente_solo_ve_lo_suyo_sin_notas_internas_ni_ocultos(app, login, db):
    cid, _contact, email, s = _invited(app, login, db)
    tid = _case_thread(s, cid)["id"]
    assert _send(s, tid, text="Le escribimos para pedirle el pasaporte.").status_code == 201
    assert _send(s, tid, text="NOTA: revisar antecedentes del empleador", visibility="interna").status_code == 201
    t = _send(s, tid, text="Mensaje enviado por error").json()
    wrong = t["messages"][-1]["id"]
    assert s.post(f"{API}/comm/messages/{wrong}/hide", json={"reason": "Enviado al cliente equivocado"}).status_code == 200
    c = _portal_login(app, email)
    threads = c.get(f"{API}/portal/threads").json()["threads"]
    case_t = next(x for x in threads if x["kind"] == "expediente")
    view = c.get(f"{API}/portal/threads/{case_t['id']}").json()
    texts = [m["text"] for m in view["messages"]]
    assert "Le escribimos para pedirle el pasaporte." in texts
    assert not any("NOTA" in x or "por error" in x for x in texts)
    # El equipo sigue viéndolo todo, marcado
    staff_view = _case_thread(s, cid)["messages"]
    hidden = next(m for m in staff_view if m["id"] == wrong)
    assert hidden["hidden"] and hidden["hidden_reason"] == "Enviado al cliente equivocado"
    # Otro cliente no puede abrir este hilo (404 y queda auditado)
    _cid2, _c2, email2, _s2 = _invited(app, login, db)
    other = _portal_login(app, email2)
    assert other.get(f"{API}/portal/threads/{case_t['id']}").status_code == 404
    assert db.execute(text("SELECT count(*) FROM audit_event WHERE action='portal.thread.denied' AND resource_id=:t"),
                      {"t": case_t["id"]}).scalar_one() >= 1


def test_nada_se_borra_y_los_textos_van_cifrados(app, login, db):
    cid, _contact, _email, s = _invited(app, login, db)
    tid = _case_thread(s, cid)["id"]
    secreto = f"Texto confidencial {uuid.uuid4().hex}"
    _send(s, tid, text=secreto)
    db.rollback()
    assert db.execute(text("SELECT count(*) FROM comm_message WHERE body_enc LIKE :s"), {"s": f"%{secreto[-10:]}%"}).scalar_one() == 0
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM comm_message WHERE thread_id = :t"), {"t": tid})
    db.rollback()


def test_pendientes_del_tramite_y_envio_para_un_requisito(app, login, db):
    from app.immigration import samples

    cid, _contact, email, s = _invited(app, login, db)
    c = _portal_login(app, email)
    case_t = next(x for x in c.get(f"{API}/portal/threads").json()["threads"] if x["kind"] == "expediente")
    assert case_t["case"]["procedure"] == "Arraigo sociolaboral" and case_t["missing_documents"] > 0
    view = c.get(f"{API}/portal/threads/{case_t['id']}").json()
    req = next(m for m in view["missing_documents"] if "empadronamiento" in m["label"].lower() or "padr" in m["label"].lower()) \
        if any("padr" in m["label"].lower() for m in view["missing_documents"]) else view["missing_documents"][0]
    r = c.post(f"{API}/portal/threads/{case_t['id']}/messages", data={"requirement_index": str(req["index"])},
               files={"files": ("padron.pdf", samples.padron(), PDF)})
    assert r.status_code == 201, r.text
    assert r.json()["messages"][-1]["text"] == f"Le envío: {req['label']}."
    # El equipo lo ve como no leído y lo pasa al expediente, donde se lee como cualquier documento
    inbox = s.get(f"{API}/comm/inbox").json()
    assert next(t for t in inbox["threads"] if t["id"] == case_t["id"])["unread"] == 1
    staff = _case_thread(s, cid)
    att = staff["messages"][-1]["attachments"][0]
    assert att["requirement_index"] == req["index"] and att["incorporated"] is False
    inc = s.post(f"{API}/comm/attachments/{att['id']}/incorporate")
    assert inc.status_code == 200, inc.text
    assert inc.json()["suggested_type"] == "empadronamiento"
    assert s.post(f"{API}/comm/attachments/{att['id']}/incorporate").status_code == 409
    docs = s.get(f"{API}/immigration/cases/{cid}").json()["documents"]
    assert any(d["original_name"] == "padron.pdf" for d in docs)
    # Ya leído: el contador vuelve a cero
    assert next(t for t in s.get(f"{API}/comm/inbox").json()["threads"] if t["id"] == case_t["id"])["unread"] == 0


# ------------------------------------------------------------------ permisos del equipo
def test_permisos_reales_en_el_servidor(app, login, db, ids):
    cid, contact, _email, s = _invited(app, login, db)
    tid = _case_thread(s, cid)["id"]
    # Asesora de extranjería sin el expediente asignado
    other = _new_case(db, procedure="ARR-SOCIAL", assignee=None)
    assert login("asesor.extranjeria.mad").get(f"{API}/comm/cases/{other}/thread").status_code == 403
    # Recepción no lee conversaciones
    assert login("recepcion.bcn").get(f"{API}/comm/threads/{tid}").status_code == 403
    # Otra entidad: no existe
    assert login("asesor.laboral.autonomo").get(f"{API}/comm/threads/{tid}").status_code == 404
    # Laboral no ve extranjería
    assert login("lider.laboral").get(f"{API}/comm/threads/{tid}").status_code == 403
    # La asesora no envía urgentes (permiso de Líder/Dirección) y no puede escribir urgentes «a mano»
    assert _send(s, tid, text="x", level="urgente").status_code == 403
    lider = login("lider.extranjeria")
    assert _send(lider, tid, text="Venga mañana sin falta", level="urgente").status_code == 422
    # Gestión del acceso al portal: Recepción no
    assert login("recepcion.bcn").post(f"{API}/comm/contacts/{contact}/portal/block",
                                       json={"block": True, "reason": "prueba"}).status_code == 403
    denied = db.execute(text("SELECT count(*) FROM audit_event WHERE outcome='denied' AND action LIKE 'comm.%'")).scalar_one()
    assert denied >= 3


# ------------------------------------------------------------------ avisos
def _task(db, cid, kind, *, start=None, deadline=None, validated=False, location=None):
    from app.models import CaseFile, UserAccount
    from app.models_work import Task

    cf = db.get(CaseFile, cid)
    u = db.execute(select(UserAccount).where(UserAccount.username == "lider.extranjeria")).scalar_one()
    t = Task(organization_id=cf.organization_id, case_id=cid, title=f"{kind} (ficticio)", kind=kind, assignee_id=u.id,
             due_at=datetime.now(UTC) + timedelta(days=5), start_at=start, end_at=(start + timedelta(hours=1)) if start else None,
             location=location, created_by=u.id, legal_deadline=deadline,
             legal_status=("validado" if validated else "pendiente_validacion") if deadline else "no_aplica",
             legal_validated_by=u.id if validated else None, legal_validated_at=datetime.now(UTC) if validated else None)
    db.add(t)
    db.commit()
    return t.id


def test_urgente_solo_con_fecha_validada_y_confirmacion(app, login, db):
    cid, _contact, email, _s = _invited(app, login, db)
    lider = login("lider.extranjeria")
    tid = _case_thread(lider, cid)["id"]
    pending = _task(db, cid, "plazo", deadline=date(2026, 12, 10))
    r = _send(lider, tid, template="requerimiento", task_id=pending)
    assert r.status_code == 409 and "no está validado" in r.json()["error"]["message"]
    ok_task = _task(db, cid, "plazo", deadline=date(2026, 12, 10), validated=True)
    r = _send(lider, tid, template="requerimiento", task_id=ok_task)
    assert r.status_code == 201, r.text
    msg = r.json()["messages"][-1]
    assert msg["level"] == "urgente" and msg["requires_confirmation"] and "10/12/2026" in msg["text"]
    cmac = _task(db, cid, "conciliacion", start=datetime(2026, 12, 3, 9, 30, tzinfo=UTC), location="CMAC de Madrid (ficticio)")
    r = _send(lider, tid, template="citacion_conciliacion", task_id=cmac)
    assert "03/12/2026 a las 10:30" in r.json()["messages"][-1]["text"]  # hora de Madrid
    # El correo al cliente NO lleva el contenido
    db.rollback()
    bodies = db.execute(text("SELECT subject, body_enc FROM comm_outbox WHERE message_id = :m"), {"m": msg["id"]}).all()
    from app.services import textcrypt

    assert bodies and "URGENTE" in textcrypt.dec(bodies[0][1]) and "10/12/2026" not in textcrypt.dec(bodies[0][1])
    # El cliente confirma una sola vez y el equipo lo ve
    c = _portal_login(app, email)
    view = c.get(f"{API}/portal/threads/{tid}").json()
    urgent = next(m for m in view["messages"] if m["id"] == msg["id"])
    assert urgent["requires_confirmation"] and urgent["confirmed_at"] is None
    c.post(f"{API}/portal/messages/{msg['id']}/confirm")
    c.post(f"{API}/portal/messages/{msg['id']}/confirm")
    assert db.execute(text("SELECT count(*) FROM comm_confirmation WHERE message_id = :m"), {"m": msg["id"]}).scalar_one() == 1
    staff_msg = next(m for m in _case_thread(lider, cid)["messages"] if m["id"] == msg["id"])
    assert staff_msg["confirmed_at"] and staff_msg["read_by_client"]


def test_urgente_sin_confirmar_en_24h_crea_una_tarea_de_llamada(app, login, db):
    cid, _contact, _email, _s = _invited(app, login, db)
    lider = login("lider.extranjeria")
    tid = _case_thread(lider, cid)["id"]
    t = _task(db, cid, "senalamiento", start=datetime(2026, 12, 15, 10, 0, tzinfo=UTC))
    mid = _send(lider, tid, template="senalamiento_juicio", task_id=t).json()["messages"][-1]["id"]
    db.execute(text("UPDATE comm_message SET created_at = now() - interval '25 hours' WHERE id = :m"), {"m": mid})
    db.commit()
    inbox = lider.get(f"{API}/comm/inbox").json()
    assert next(x for x in inbox["threads"] if x["id"] == tid)["urgent_unconfirmed"] == 1
    lider.get(f"{API}/comm/inbox")  # el escalado no se repite
    tasks = db.execute(text("SELECT t.kind, t.case_id FROM task t JOIN comm_message m ON m.escalated_task_id = t.id "
                            "WHERE m.id = :m"), {"m": mid}).all()
    assert len(tasks) == 1 and tasks[0][0] == "llamada" and str(tasks[0][1]) == str(cid)
    assert db.execute(text("SELECT count(*) FROM task WHERE title LIKE 'Llamar al cliente%' AND case_id = :c"),
                      {"c": cid}).scalar_one() == 1


def test_importante_sin_abrir_48h_se_marca(app, login, db):
    cid, _contact, _email, s = _invited(app, login, db)
    tid = _case_thread(s, cid)["id"]
    mid = _send(s, tid, text="Recuerde traer la nómina", level="importante").json()["messages"][-1]["id"]
    db.execute(text("UPDATE comm_message SET created_at = now() - interval '49 hours' WHERE id = :m"), {"m": mid})
    db.commit()
    assert next(m for m in _case_thread(s, cid)["messages"] if m["id"] == mid)["unopened_48h"] is True


def test_correos_del_dia_a_dia_agrupados_por_hora(app, login, db):
    cid, _contact, email, s = _invited(app, login, db)
    tid = _case_thread(s, cid)["id"]
    for i in range(3):
        _send(s, tid, text=f"Mensaje {i}")
    db.rollback()
    n = db.execute(text("SELECT count(*) FROM comm_outbox WHERE purpose='aviso' AND to_address=:e"), {"e": email}).scalar_one()
    assert n == 1


# ------------------------------------------------------------------ correcciones y ediciones
def test_correccion_15_minutos_con_version_guardada(app, login, db):
    cid, _contact, email, s = _invited(app, login, db)
    tid = _case_thread(s, cid)["id"]
    mid = _send(s, tid, text="Su cita es el martes").json()["messages"][-1]["id"]
    r = s.patch(f"{API}/comm/messages/{mid}", json={"text": "Su cita es el miércoles"})
    assert r.status_code == 200
    m = next(x for x in r.json()["messages"] if x["id"] == mid)
    assert m["text"] == "Su cita es el miércoles" and m["version"] == 2
    vers = s.get(f"{API}/comm/messages/{mid}/versions").json()["versions"]
    assert vers == [{"version": 1, "text": "Su cita es el martes", "replaced_at": vers[0]["replaced_at"]}]
    # Otra persona no lo corrige; fuera de plazo tampoco
    assert login("lider.extranjeria").patch(f"{API}/comm/messages/{mid}", json={"text": "x"}).status_code == 403
    db.execute(text("UPDATE comm_message SET created_at = now() - interval '16 minutes' WHERE id = :m"), {"m": mid})
    db.commit()
    assert s.patch(f"{API}/comm/messages/{mid}", json={"text": "y"}).status_code == 409
    # El cliente corrige lo suyo
    c = _portal_login(app, email)
    w = c.post(f"{API}/portal/threads/{tid}/messages", data={"text": "Hola, soy yo"}).json()["messages"][-1]
    assert w["can_edit"]
    assert c.patch(f"{API}/portal/messages/{w['id']}", json={"text": "Hola, soy Carla"}).status_code == 200
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE comm_message_version SET body_enc = 'x' WHERE message_id = :m"), {"m": mid})
    db.rollback()


# ------------------------------------------------------------------ exportación
def test_exportacion_con_huella_y_alcance(app, login, db):
    cid, _contact, _email, s = _invited(app, login, db)
    tid = _case_thread(s, cid)["id"]
    _send(s, tid, text="Mensaje para el cliente (ficticio)")
    _send(s, tid, text="NOTA INTERNA secreta (ficticia)", visibility="interna")
    a = s.get(f"{API}/comm/threads/{tid}/export.pdf")
    b = s.get(f"{API}/comm/threads/{tid}/export.pdf")
    assert a.status_code == 200 and a.headers["x-content-sha256"] == b.headers["x-content-sha256"]
    full = s.get(f"{API}/comm/threads/{tid}/export.pdf", params={"scope": "completo"})
    assert full.headers["x-content-sha256"] != a.headers["x-content-sha256"]

    def txt(pdf: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf)
            f.flush()
            return subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True).stdout

    assert "secreta" not in txt(a.content) and "Mensaje para el cliente" in txt(a.content)
    assert "secreta" in txt(full.content) and a.headers["x-content-sha256"] in txt(a.content)
    # Exportar exige su permiso (el gestor laboral no lo tiene) y queda en la auditoría
    assert db.execute(text("SELECT count(*) FROM audit_event WHERE action='comm.export' AND resource_id=:t"),
                      {"t": tid}).scalar_one() == 3


# ------------------------------------------------------------------ cola de envíos y bloqueo
class _FakeMail:
    configured = True

    def __init__(self, fail: bool = False):
        self.sent: list[tuple[str, str, str]] = []
        self.fail = fail

    def send(self, to, subject, body):
        if self.fail:
            raise OSError("servidor de correo caído (simulado)")
        self.sent.append((to, subject, body))


def test_cola_de_envios_idempotente_con_reintentos(app, login, db):
    from app.services import notify

    fake = _FakeMail()
    notify.set_adapter_for_tests(fake)
    try:
        cid = _new_case(db, procedure="ARR-SOCIAL")
        contact, email = _with_email(db, cid)
        s = login("asesor.extranjeria.mad")
        s.post(f"{API}/comm/contacts/{contact}/portal/invite", json={"email": email})
        notify.dispatch_pending()
        notify.dispatch_pending()
        mine = [m for m in fake.sent if m[0] == email]
        assert len(mine) == 1 and "portal" in mine[0][2]
        c = _client(app)
        c.post(f"{API}/portal/auth/request-code", json={"email": email})
        notify.dispatch_pending()
        code_mail = [m for m in fake.sent if m[0] == email and "código" in m[1]]
        assert code_mail and any(ch.isdigit() for ch in code_mail[0][2])
        # Con correo configurado el código ya no se muestra en pantalla
        assert "dev_code" not in c.post(f"{API}/portal/auth/request-code", json={"email": email}).json()
        broken = _FakeMail(fail=True)
        notify.set_adapter_for_tests(broken)
        tid = _case_thread(s, cid)["id"]
        _send(s, tid, text="Hola (ficticio)", level="importante")
        notify.dispatch_pending()
        db.rollback()
        st, att, err = db.execute(text("SELECT status, attempts, last_error FROM comm_outbox WHERE to_address=:e AND purpose='aviso'"),
                                  {"e": email}).one()
        assert st == "error" and 1 <= att <= notify.MAX_ATTEMPTS and "caído" in err  # reintenta, sin pasar del máximo
    finally:
        notify.set_adapter_for_tests(None)


def test_bloquear_cierra_sesiones_y_no_da_codigos(app, login, db):
    _cid, contact, email, s = _invited(app, login, db)
    c = _portal_login(app, email)
    assert c.get(f"{API}/portal/threads").status_code == 200
    r = s.post(f"{API}/comm/contacts/{contact}/portal/block", json={"block": True, "reason": "Cliente lo ha pedido"})
    assert r.status_code == 200 and r.json()["status"] == "bloqueada"
    assert c.get(f"{API}/portal/threads").status_code == 401
    assert "dev_code" not in _client(app).post(f"{API}/portal/auth/request-code", json={"email": email}).json()
    r = s.post(f"{API}/comm/contacts/{contact}/portal/block", json={"block": False})
    assert r.json()["status"] == "activa"


def test_aviso_con_plantilla_no_se_corrige(app, login, db):
    cid, _contact, _email, _s = _invited(app, login, db)
    lider = login("lider.extranjeria")
    tid = _case_thread(lider, cid)["id"]
    t = _task(db, cid, "conciliacion", start=datetime(2026, 12, 3, 9, 30, tzinfo=UTC))
    m = _send(lider, tid, template="citacion_conciliacion", task_id=t).json()["messages"][-1]
    assert m["can_edit"] is False
    assert lider.patch(f"{API}/comm/messages/{m['id']}", json={"text": "otra fecha"}).status_code == 409
