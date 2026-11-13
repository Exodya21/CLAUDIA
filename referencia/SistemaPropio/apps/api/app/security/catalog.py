"""Catálogo de permisos y roles F0.1.

Traducción operativa de la hoja ROLES_PERMISOS de la matriz (A/P/M/S/N).
REQUIERE aprobación de Dirección y DPO (D-13, D-17). Denegar por defecto: si un
permiso no figura aquí para un rol, no existe.
"""

from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    "contact.search": "Buscar identidades y ver ficha mínima (datos enmascarados) [M]",
    "contact.read.all": "Ver ficha completa de cualquier contacto de la entidad [A]",
    "contact.read.own": "Ver ficha completa de contactos propios o con expediente accesible [P]",
    "contact.create": "Dar de alta contactos",
    "contact.update": "Modificar datos de contacto no identificativos",
    "contact.identifier.manage": "Añadir o modificar documentos de identidad (dato sensible)",
    "case.metadata.read": "Ver metadatos de expedientes (código, materia, estado) sin contenido [M]",
    "case.read.all": "Leer cualquier expediente de la entidad [A]",
    "case.read.department": "Leer expedientes de su departamento (y sede si está acotado) [A en su rama]",
    "case.read.assigned": "Leer expedientes asignados o con autorización puntual vigente [P/S]",
    "grant.manage": "Conceder y revocar autorizaciones puntuales con motivo y caducidad",
    "audit.read": "Consultar la bitácora de auditoría",
    # F1.2 CRM
    "lead.create": "Registrar leads (origen obligatorio)",
    "lead.read.all": "Ver todos los leads de la entidad",
    "lead.read.own": "Ver los leads asignados o creados por uno mismo",
    "lead.transition": "Cambiar el estado de un lead visible",
    "lead.funnel": "Ver el embudo comercial agregado",
    # F2.1 expedientes
    "case.create": "Abrir expedientes de su departamento (y sede si está acotado)",
    "case.transition": "Cambiar fases operativas de expedientes accesibles (apertura, trámite, suspensión)",
    "case.transition.legal": "Fases con efecto jurídico: resuelto, en ejecución, desistido, archivado",
    "case.assign": "Asignar y retirar responsables de expedientes accesibles",
    # F2.2 tareas
    "task.create": "Crear tareas en expedientes accesibles o propias",
    "task.manage.others": "Modificar o reasignar tareas de otras personas en su ámbito (Q-6.23)",
    "task.cancel": "Anular tareas (con motivo)",
    "deadline.validate": "Validar fechas legales propuestas (función de letrado)",
    # F0.2 administración y operación
    "admin.users.manage": "Dar de alta, desactivar y asignar roles a usuarios de su entidad; cerrar sus sesiones",
    "admin.backups.read": "Consultar el registro de copias de seguridad y sus comprobaciones de restauración",
    # F5.0 control económico (no fiscal: no emite facturas)
    "economy.read.all": "Ver la situación económica de todos los expedientes de la entidad (sin contenido jurídico)",
    "economy.read.case": "Ver la situación económica de los expedientes con acceso completo",
    "charge.create": "Registrar importes pactados pendientes de cobro (los introduce una persona; no se calculan)",
    "charge.cancel": "Anular importes pendientes de cobro (con motivo)",
    "payment.register": "Registrar cobros recibidos en expedientes visibles",
    "payment.confirm": "Confirmar o anular cobros (conciliación) y anotar el nº de factura del programa homologado",
    "refund.request": "Registrar solicitudes de devolución de clientes",
    "refund.review": "Investigar y escalar devoluciones (no las aprueba)",
    "refund.legal_opinion": "Emitir informe jurídico sobre una devolución escalada (no la aprueba)",
    "refund.decide": "Aprobar o rechazar devoluciones y registrar su pago (Contabilidad, A-09)",
    "cash.operate": "Registrar movimientos y arqueos de la caja de su sede",
    "cash.read.all": "Ver las cajas de todas las sedes de la entidad",
    "economy.report": "Ver el resumen económico por sede y periodo",
    # F5.0 gastos de empresa
    "expense.submit": "Subir sus propios gastos con justificante",
    "expense.review": "Revisar, aprobar, devolver y conciliar gastos; gestionar tarjetas e importar extractos",
    "expense.read.all": "Ver todos los gastos de la entidad y su resumen mensual",
    # F4.1 extranjería
    "immig.document.upload": "Subir documentación a expedientes de extranjería visibles (Recepción: sin poder verla después)",
    "immig.document.review": "Confirmar tipo, fechas y validez de los documentos de extranjería",
    "immig.package": "Preparar y descargar el paquete de documentos para Mercurio",
    "immig.catalog.approve": "Validar el catálogo de trámites y sus listas de documentos (Legal Extranjería)",
    "immig.office.manage": "Datos del despacho como representante en las solicitudes de extranjería (modelos EX y Mercurio)",
    # F2.3 + M12 comunicaciones con el cliente (portal propio, sin WhatsApp: T-31)
    "comm.read": "Leer las conversaciones de los expedientes con acceso completo (y el hilo general de sus clientes)",
    "comm.send": "Escribir al cliente en esas conversaciones, adjuntar archivos y ocultar mensajes (sin borrarlos)",
    "comm.note": "Escribir notas internas que el cliente no ve",
    "comm.notice.important": "Enviar avisos importantes (aviso por correo, sin contenido)",
    "comm.notice.urgent": "Enviar avisos urgentes con confirmación de lectura (citaciones, plazos validados)",
    "comm.portal.invite": "Dar acceso al portal a un cliente, y bloquearlo o reactivarlo",
    "comm.export": "Exportar una conversación con su huella digital",
    # F5.1 agentes y banco (documentos de Dirección 08/11/2026)
    "agents.view": "Ver los agentes, su actividad y sus límites",
    "agents.manage": "Activar o pausar agentes y elegir su modo (propone / automático donde se permite, T-47)",
    "bank.read": "Ver cuentas bancarias, extractos, movimientos y su conciliación",
    "bank.import": "Importar extractos bancarios (Norma 43, CAMT.053, CSV)",
    "bank.reconcile": "Validar o rechazar emparejamientos, conciliar a mano y justificar movimientos",
    "bank.accounts.manage": "Dar de alta y desactivar cuentas bancarias (A laboral, B extranjería, C tesorería)",
    # F5.2 Recepción
    "reception.balance": "Ver lo que queda por cobrar de un expediente (solo importes, sin contenido) para cobrarlo",
    "cash.close.validate": "Validar o rechazar el cierre diario de caja de una sede (nunca el propio)",
    # F5.3 RRHH (datos de personal aislados de los de clientes)
    "hr.self": "Ver su propia ficha, sus nóminas y documentos, y pedir vacaciones o permisos",
    "hr.read": "Ver la plantilla (ficha laboral sin salario ni datos de salud)",
    "hr.manage": "Alta y cambios de fichas, carpeta documental, ausencias de cualquiera, avisos e importación",
    "hr.salary": "Ver y revisar salarios y nóminas; resumen mensual para la gestoría",
    "hr.leave.decide": "Aprobar o rechazar vacaciones y permisos (su departamento, o toda la plantilla con hr.manage)",
    # F5.4 Contabilidad (proveedores, tesorería y cierre del mes)
    "supplier.manage": "Dar de alta y modificar proveedores (CIF e IBAN comprobados)",
    "invoice.register": "Registrar facturas recibidas con su original",
    "invoice.validate": "Validar o rechazar facturas recibidas (datos, actividad, oficina y centro de coste)",
    "treasury.read": "Ver saldos, previsión de pagos y remesas",
    "treasury.propose": "Proponer remesas de pago a proveedores",
    "treasury.approve": "Autorizar remesas (hacen falta dos personas distintas de quien la propone)",
    "accounting.read": "Ver el cuadro de mando económico y los cierres del mes",
    "accounting.close": "Preparar y revisar el cierre provisional del mes",
    "accounting.close.approve": "Aprobar el cierre provisional del mes (persona distinta de quien lo preparó)",
}

# rol -> (nombre, descripción, permisos)
ROLES: dict[str, tuple[str, str, list[str]]] = {
    "direccion": (
        "Dirección",
        "Visión global de la entidad; autoriza excepciones. Sus accesos también se auditan.",
        [
            "contact.search", "contact.read.all", "contact.create", "contact.update",
            "contact.identifier.manage", "case.metadata.read", "case.read.all",
            "grant.manage", "audit.read",
            "lead.create", "lead.read.all", "lead.transition", "lead.funnel",
            "case.create", "case.transition", "case.transition.legal", "case.assign",
            "task.create", "task.manage.others", "task.cancel", "deadline.validate",
            "admin.users.manage", "admin.backups.read",
            "economy.read.all", "charge.create", "charge.cancel", "payment.register", "refund.request", "refund.legal_opinion", "cash.read.all", "economy.report", "expense.submit", "expense.read.all", "immig.document.upload", "immig.document.review", "immig.package", "immig.catalog.approve", "immig.office.manage",
            "comm.read", "comm.send", "comm.note", "comm.notice.important", "comm.notice.urgent", "comm.portal.invite", "comm.export",
            "agents.view", "agents.manage", "bank.read", "bank.accounts.manage", "cash.close.validate", "hr.self", "hr.read", "hr.manage", "hr.salary", "hr.leave.decide", "supplier.manage", "invoice.validate", "treasury.read", "treasury.approve", "accounting.read", "accounting.close.approve"],
    ),
    "lider_laboral": (
        "Líder Laboral",
        "Todos los expedientes Laborales de su ámbito; nunca Extranjería. Valida fechas legales de su rama.",
        ["contact.search", "contact.read.own", "contact.create", "contact.update", "case.read.department",
         "lead.create", "lead.read.all", "lead.transition", "lead.funnel",
         "case.create", "case.transition", "case.transition.legal", "case.assign",
         "task.create", "task.manage.others", "task.cancel", "deadline.validate", "economy.read.case", "charge.create", "payment.register", "refund.request", "refund.legal_opinion", "expense.submit", "agents.view",
         "comm.read", "comm.send", "comm.note", "comm.notice.important", "comm.notice.urgent", "comm.portal.invite", "comm.export", "hr.leave.decide", "hr.self"],
    ),
    "lider_extranjeria": (
        "Líder Extranjería",
        "Todos los expedientes de Extranjería de su ámbito; nunca Laboral. Valida plazos y el catálogo de trámites.",
        ["contact.search", "contact.read.own", "contact.create", "contact.update", "contact.identifier.manage",
         "case.read.department", "lead.create", "lead.read.all", "lead.transition", "lead.funnel",
         "case.create", "case.transition", "case.transition.legal", "case.assign",
         "task.create", "task.manage.others", "task.cancel", "deadline.validate",
         "economy.read.case", "charge.create", "payment.register", "refund.request", "refund.legal_opinion",
         "expense.submit", "agents.view", "immig.document.upload", "immig.document.review", "immig.package", "immig.catalog.approve", "immig.office.manage",
         "comm.read", "comm.send", "comm.note", "comm.notice.important", "comm.notice.urgent", "comm.portal.invite", "comm.export", "hr.leave.decide", "hr.self"],
    ),
    "recepcion": (
        "Recepción",
        "Localiza identidades, crea contactos y leads; ve metadatos de expedientes, nunca su contenido (D-13).",
        ["contact.search", "contact.create", "case.metadata.read", "lead.create", "lead.read.all", "lead.transition", "payment.register", "refund.request", "cash.operate", "expense.submit", "immig.document.upload", "reception.balance", "hr.self"],
    ),
    "atc": (
        "Atención al cliente",
        "Registra y escala; no decide viabilidad ni aprueba devoluciones (U-13).",
        ["contact.search", "case.metadata.read", "lead.create", "lead.read.all", "lead.transition", "refund.request", "refund.review", "expense.submit", "hr.self"],
    ),
    "asesor_laboral": (
        "Asesor Laboral",
        "Contactos, leads y expedientes Laborales asignados.",
        ["contact.search", "contact.read.own", "contact.create", "contact.update", "case.read.assigned",
         "lead.create", "lead.read.own", "lead.transition", "case.create", "case.transition", "task.create", "economy.read.case", "charge.create", "payment.register", "refund.request", "expense.submit",
         "comm.read", "comm.send", "comm.note", "comm.notice.important", "comm.portal.invite", "comm.export", "hr.self"],
    ),
    "asesor_extranjeria": (
        "Asesor Extranjería",
        "Contactos, leads y expedientes de Extranjería asignados.",
        ["contact.search", "contact.read.own", "contact.create", "contact.update", "case.read.assigned",
         "lead.create", "lead.read.own", "lead.transition", "case.create", "case.transition", "task.create", "economy.read.case", "charge.create", "payment.register", "refund.request", "expense.submit", "immig.document.upload", "immig.document.review", "immig.package",
         "comm.read", "comm.send", "comm.note", "comm.notice.important", "comm.portal.invite", "comm.export", "hr.self"],
    ),
    "gestor_laboral": (
        "Gestor Laboral",
        "Tramitación de expedientes Laborales asignados; gestiona documentos de identidad.",
        ["contact.search", "contact.read.own", "contact.update", "contact.identifier.manage",
         "case.read.assigned", "case.transition", "task.create", "economy.read.case", "expense.submit",
         "comm.read", "comm.send", "comm.note", "comm.notice.important", "hr.self"],
    ),
    "contabilidad": (
        "Contabilidad",
        "Economía de todos los expedientes (sin contenido jurídico), cobros, devoluciones, cajas y gastos. Decide devoluciones (A-09).",
        ["contact.search", "case.metadata.read", "economy.read.all", "charge.create", "charge.cancel", "payment.register", "payment.confirm", "refund.review", "refund.decide", "cash.operate", "cash.read.all", "economy.report", "expense.submit", "expense.review", "expense.read.all",
         "agents.view", "bank.read", "bank.import", "bank.reconcile", "bank.accounts.manage", "cash.close.validate", "hr.self", "supplier.manage", "invoice.register", "invoice.validate", "treasury.read", "treasury.propose", "accounting.read", "accounting.close"],
    ),
    "marketing": (
        "Marketing",
        "Leads, orígenes y embudo. Sin acceso a expedientes, pruebas ni documentos.",
        ["contact.search", "lead.create", "lead.read.all", "lead.funnel", "expense.submit", "hr.self"],
    ),
    "rrhh": (
        "Recursos Humanos",
        "Plantilla, carpetas, nóminas (sin calcularlas), ausencias y vencimientos. Sin acceso a expedientes de clientes.",
        ["hr.self", "hr.read", "hr.manage", "hr.salary", "hr.leave.decide", "agents.view", "task.create", "expense.submit"],
    ),
    "soporte_colombia": (
        "Soporte Colombia",
        "Solo su alcance asignado. Acceso a datos de entidades españolas pendiente de D-17.",
        ["contact.search", "contact.read.own", "case.read.assigned", "expense.submit", "hr.self"],
    ),
}

for _code, (_n, _d, _perms) in ROLES.items():
    _unknown = set(_perms) - set(PERMISSIONS)
    assert not _unknown, f"Permisos desconocidos en {_code}: {_unknown}"
