// Navegación y estado real de cada módulo. Los módulos no construidos se muestran como
// "Pendiente de desarrollar" con sus requisitos vinculados: nunca simulan resultados.

export interface ModuleInfo {
  slug: string;
  label: string;
  code: string;
  status: "operativo" | "parcial" | "pendiente";
  fase: string;
  requisitos: string[];
  pruebas: string[];
  decisiones: string[];
  resumen: string;
  /** Si se indica, el menú solo lo muestra a quien tenga ese permiso (el servidor lo exige igualmente). */
  perm?: string;
  /** Alternativa: se muestra si tiene cualquiera de estos permisos. */
  anyPerm?: string[];
}

export const MODULES: ModuleInfo[] = [
  { slug: "", label: "Inicio", code: "M00", status: "operativo", fase: "F0.1", requisitos: ["U-18"], pruebas: [], decisiones: [],
    resumen: "Panel según rol con datos reales." },
  { slug: "clientes", label: "Clientes", code: "M01", status: "operativo", fase: "F0.1", requisitos: ["I-003", "Q-1.2"],
    pruebas: ["AT-02", "AT-04"], decisiones: ["D-13"], resumen: "Búsqueda, alta con aviso de duplicados y ficha." },
  { slug: "crm", label: "CRM", code: "M02", status: "operativo", fase: "F1.2",
    requisitos: ["Q-2.1", "Q-2.2", "Q-2.7", "Q-2.8", "Q-3.1", "I-099", "I-102"], pruebas: ["AT-05", "AT-06"], decisiones: [],
    resumen: "Leads con origen obligatorio, embudo lead → cita pagada → expediente y alertas de oportunidades estancadas." },
  { slug: "citas", label: "Citas", code: "M03", status: "pendiente", fase: "F1.3",
    requisitos: ["Q-2.4", "Q-2.5", "Q-2.6", "Q-3.7", "U-14", "I-069"], pruebas: ["AT-07", "AT-08", "AT-09"],
    decisiones: ["D-11", "D-19"], resumen: "Agenda propia, filtrado por rama/sede/modalidad, cobro previo con pasarela en modo prueba." },
  { slug: "fichas-laborales", label: "Fichas laborales", code: "M04", status: "pendiente", fase: "F2",
    requisitos: ["I-004", "I-006", "Q-2.9", "Q-6.1", "U-01", "U-02", "U-04", "U-08", "U-09", "U-12"],
    pruebas: ["AT-10", "AT-11", "AT-12", "AT-13", "AT-14"], decisiones: ["D-12"],
    resumen: "Tres rutas: régimen general con papeles, sin papeles y hogar sin papeles. Requiere protocolos Laboral aprobados." },
  { slug: "expedientes", label: "Expedientes", code: "M05", status: "operativo", fase: "F2.1",
    requisitos: ["Q-6.2", "I-007", "I-010"], pruebas: ["AT-01"], decisiones: [],
    resumen: "Apertura desde cliente o lead, fases por rol, responsables, relaciones e inactividad." },
  { slug: "extranjeria", label: "Extranjería", code: "M11", status: "parcial", fase: "F4.1–F4.3",
    requisitos: ["I-007", "I-010", "I-078", "I-079", "I-083", "I-087", "Q-6.2", "Q-6.6"], pruebas: ["AT-17"],
    decisiones: ["D-01", "D-03", "D-09", "D-22"], anyPerm: ["immig.document.review", "immig.package", "immig.catalog.approve"],
    resumen: "Bandeja de trámites por fase, documentos leídos (MRZ) con confirmación humana, avisos de caducidad, paquete para Mercurio, lectura de contrato, padrón, TIE y tasa que propone los datos (también del empleador), ficha del formulario EX y extensión que rellena Mercurio (sin presentar), catálogo validado por Legal. Sin presentación ni descarga automática en portales." },
  { slug: "agenda", label: "Agenda", code: "M09", status: "operativo", fase: "F2.2",
    requisitos: ["I-067", "I-073", "I-076", "Q-6.9", "Q-6.10", "Q-6.15", "Q-6.20", "Q-6.20B", "U-16"],
    pruebas: ["AT-19", "AT-20"], decisiones: ["D-02", "D-03", "D-04", "D-21"],
    resumen: "Tareas, señalamientos y vencimientos. Fecha legal y objetivo interno separados; ningún plazo legal sin validación letrada." },
  { slug: "documentos", label: "Documentos", code: "M07", status: "pendiente", fase: "F2",
    requisitos: ["I-078", "I-079", "Q-3.10", "Q-6.6", "Q-6.7", "Q-6.13", "Q-6.14", "Q-6.22"],
    pruebas: ["AT-17", "AT-32"], decisiones: ["D-08", "D-22"],
    resumen: "Almacenamiento cifrado, versiones, hash, antivirus, enlaces caducables y portal de pruebas." },
  { slug: "comunicaciones", label: "Comunicaciones", code: "M12", status: "parcial", fase: "F2.3", anyPerm: ["comm.read"],
    requisitos: ["I-090", "I-091", "I-093", "I-096", "I-097", "Q-3.3", "Q-6.3", "Q-6.13", "Q-6.18", "U-15"], pruebas: ["AT-23"],
    decisiones: ["T-31", "D-10", "D-20"],
    resumen: "Portal propio del cliente (sin WhatsApp, T-31): conversación por expediente y general, notas internas, adjuntos que pasan al expediente, avisos importantes y urgentes con confirmación y escalado, correo sin contenido, exportación con huella. Pendiente: SMS, notas de voz, centralita, importación de WhatsApp." },
  { slug: "economia", label: "Economía", code: "M14", status: "parcial", fase: "F5.0",
    requisitos: ["Q-3.9", "Q-4.4", "Q-4.14", "Q-2.6", "I-101", "I-110"], pruebas: [], decisiones: ["D-05", "D-16", "D-18", "D-25"],
    anyPerm: ["payment.register", "refund.request", "refund.review", "refund.decide", "economy.read.all", "cash.operate", "economy.report"],
    resumen: "Control económico interno sin facturas fiscales: importes pactados, cobros, devoluciones (Contabilidad decide), cajas por sede y resumen." },
  { slug: "gastos", label: "Gastos", code: "M14", status: "operativo", fase: "F5.0",
    requisitos: ["Q-4.13", "Q-4.14", "Q-4.5", "I-079"], pruebas: [], decisiones: ["D-25"], perm: "expense.submit",
    resumen: "Tickets y facturas de gasto con lectura automática propuesta, revisión de Contabilidad y conciliación con caja y tarjetas." },
  { slug: "recepcion", label: "Recepción", code: "M13", status: "parcial", fase: "F5.2",
    requisitos: ["Q-4.4", "Q-4.14", "I-101", "DR-REC-3", "DR-REC-4", "DR-REC-8", "DR-REC-9", "DR-REC-10"], pruebas: [],
    decisiones: ["T-44", "D-07", "D-25"], anyPerm: ["cash.operate", "cash.read.all", "cash.close.validate"],
    resumen: "Cobros de consulta (también sin expediente), provisión y servicio con justificante numerado que no es factura, aviso de cobros repetidos, caja del día con cierre validado por un responsable e informe diario o semanal por sede. Pendiente: citas y llegada de clientes (F5.5)." },
  { slug: "contabilidad", label: "Contabilidad", code: "M14", status: "operativo", fase: "F5.4",
    requisitos: ["Q-4.5", "Q-4.12", "I-074", "I-075", "DR-CON-1", "DR-CON-2", "DR-CON-3", "DR-CON-4", "DR-CON-5", "DR-CON-7", "DR-CON-8"], pruebas: [],
    decisiones: ["T-38", "T-39", "T-40", "T-48", "T-53", "T-54"], anyPerm: ["bank.read", "treasury.read", "accounting.read"],
    resumen: "Rutina de trabajo con comprobación automática y tareas en la Agenda; informes semanales, quincenales y mensuales; banco y conciliación (también pagos a proveedores y remesas), facturas recibidas con lectura y duplicados, tesorería con previsión y remesas de doble firma con fichero SEPA, y cierre provisional del mes por actividad y oficina con fiabilidad. Operativo con datos ficticios; dependen de decisiones externas: asientos (plan de cuentas, T-40) y entrada de facturas por correo (T-48)." },
  { slug: "facturacion", label: "Facturación", code: "M14", status: "pendiente", fase: "F5",
    requisitos: ["Q-4.1", "Q-4.2", "Q-4.7", "Q-4.8", "Q-6.19", "Q-6.21"], pruebas: ["AT-25", "AT-31"],
    decisiones: ["D-05", "D-06", "D-07", "D-16", "D-18", "D-25"],
    resumen: "Emisión de facturas: se hará con un programa homologado para VeriFactu conectado al sistema (decisión D-25, comparativa en preparación). No se construye un facturador propio." },
  { slug: "rrhh", label: "RRHH", code: "M15", status: "parcial", fase: "F5.3",
    requisitos: ["Q-5.1", "Q-5.2", "Q-5.3", "Q-5.5", "Q-5.6", "DR-RH-1", "DR-RH-2", "DR-RH-4", "DR-RH-5", "DR-RH-6"], pruebas: ["AT-26"],
    decisiones: ["T-41", "T-49", "T-50"], anyPerm: ["hr.self", "hr.read", "hr.leave.decide"],
    resumen: "Ficha única por persona, carpeta de documentos con lectura de nóminas que confirma RRHH, vacaciones y ausencias con saldo y aprobación de otra persona, avisos de vencimientos, resumen de nóminas para la gestoría (sin calcularlas) e importación desde hoja con duplicados. Pendiente: control horario (T-41), festivos por sede (T-49), formación (DR-RH-7) y cuadro de mando (DR-RH-8)." },
  { slug: "direccion", label: "Dirección", code: "M16", status: "pendiente", fase: "F4",
    requisitos: ["I-099", "I-101", "I-102", "I-108", "I-110"], pruebas: ["AT-27"], decisiones: [],
    resumen: "Cuadro de mando por sede, asesor y periodo calculado sobre los mismos registros operativos." },
  { slug: "administracion", label: "Administración", code: "M00", status: "operativo", fase: "F0.2",
    requisitos: ["Q-1.2", "I-120", "Q-6.23"], pruebas: ["AT-29"], decisiones: ["T-01", "T-02", "T-08"], anyPerm: ["admin.users.manage", "agents.manage"],
    resumen: "Usuarios, roles por entidad/sede/departamento, sesiones activas, copias de seguridad comprobadas y configuración de los agentes automáticos." },
  { slug: "ajustes", label: "Ajustes", code: "M00", status: "operativo", fase: "F0.1", requisitos: ["Q-1.2", "Q-6.17"],
    pruebas: ["AT-03"], decisiones: [], resumen: "Perfil, seguridad de acceso, permisos efectivos, autorizaciones y auditoría (según rol)." },
];

export function moduleBySlug(slug: string): ModuleInfo | undefined {
  return MODULES.find((m) => m.slug === slug);
}
