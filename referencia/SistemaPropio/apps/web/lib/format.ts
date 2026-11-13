// La API trabaja en UTC; la interfaz muestra siempre la hora de Europe/Madrid.
export const TIMEZONE = "Europe/Madrid";

const dateTimeFmt = new Intl.DateTimeFormat("es-ES", {
  timeZone: TIMEZONE, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
});
const dateFmt = new Intl.DateTimeFormat("es-ES", { timeZone: TIMEZONE, day: "2-digit", month: "2-digit", year: "numeric" });

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : dateTimeFmt.format(d);
}

export function fmtDate(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  // Fechas sin hora (nacimiento): se interpretan como fecha civil, sin desplazamiento horario.
  const [y, m, d] = isoDate.split("-");
  return y && m && d ? `${d}/${m}/${y}` : "—";
}

export const MATERIAS: Record<string, string> = {
  laboral: "Laboral", extranjeria: "Extranjería", nacionalidad: "Nacionalidad",
};

export const ESTADOS_EXPEDIENTE: Record<string, string> = {
  preapertura: "Preapertura", abierto: "Abierto", en_tramite: "En trámite", archivado: "Archivado",
};

export const ACCIONES_AUDITORIA: Record<string, string> = {
  "auth.login": "Inicio de sesión",
  "contact.search": "Búsqueda de clientes",
  "contact.create": "Alta de cliente",
  "contact.update": "Modificación de cliente",
  "contact.read": "Consulta de ficha completa",
  "contact.duplicate_flagged": "Posible duplicado registrado",
  "case.read": "Consulta de expediente",
  "grant.create": "Autorización concedida",
  "grant.revoke": "Autorización revocada",
  "seed.load": "Carga de datos ficticios",
  "lead.create": "Alta de lead", "lead.transition": "Cambio de estado de lead", "lead.assign": "Reasignación de lead", "lead.read": "Consulta de lead",
  "case.create": "Apertura de expediente", "case.transition": "Cambio de fase", "case.assign": "Asignación de responsable",
  "case.unassign": "Retirada de responsable", "case.relate": "Relación entre expedientes",
  "task.create": "Alta de tarea", "task.transition": "Cambio de tarea", "task.read": "Consulta de tarea",
  "deadline.propose": "Plazo legal propuesto", "deadline.validate": "Plazo legal validado", "deadline.reject": "Plazo legal rechazado",
  "auth.logout": "Cierre de sesión", "auth.mfa_enroll": "Doble verificación activada", "auth.password_change": "Cambio de contraseña",
  "auth.oidc_link": "Cuenta corporativa enlazada", "session.revoke": "Sesión cerrada a distancia",
  "admin.user_create": "Alta de usuario", "admin.user_update": "Modificación de usuario", "admin.user_deactivate": "Usuario desactivado",
  "admin.user_reactivate": "Usuario reactivado", "admin.user_reset": "Credenciales restablecidas",
  "admin.membership_add": "Rol asignado", "admin.membership_end": "Rol retirado", "admin.bootstrap": "Primera administración",
  "admin.users.list": "Listado de usuarios", "admin.catalog": "Catálogo de administración", "admin.backups": "Consulta de copias",
  "backup.verify": "Copia de seguridad comprobada",
  "economy.read": "Consulta económica de expediente", "charge.create": "Importe pactado", "charge.cancel": "Importe anulado",
  "payment.register": "Cobro registrado", "payment.confirm": "Cobro confirmado", "payment.annul": "Cobro anulado",
  "refund.request": "Devolución solicitada", "refund.en_revision": "Devolución en revisión", "refund.escalada_legal": "Devolución escalada a letrado",
  "refund.aprobada": "Devolución aprobada", "refund.rechazada": "Devolución rechazada", "refund.pagada": "Devolución pagada",
  "cash.movement": "Movimiento de caja", "cash.closing": "Arqueo de caja",
  "expense.create": "Gasto subido", "expense.update": "Gasto corregido", "expense.submit": "Gasto enviado", "expense.aprobar": "Gasto aprobado",
  "expense.devolver": "Gasto devuelto", "expense.anular": "Gasto anulado", "expense.annul": "Gasto descartado", "expense.reconcile": "Gasto conciliado",
  "expense.receipt": "Consulta de justificante", "expense.export": "Exportación de gastos", "card.create": "Tarjeta de empresa registrada",
  "card.import": "Extracto de tarjeta importado",
  "immig.read": "Consulta de extranjería", "immig.setup": "Trámite de extranjería asignado", "immig.update": "Datos de presentación",
  "immig.upload": "Subida de documentos", "immig.document.upload": "Documento subido", "immig.document.read": "Consulta de documento",
  "immig.document.review": "Documento revisado", "immig.document.retire": "Documento retirado", "immig.package": "Paquete Mercurio preparado",
  "immig.catalog.approve": "Lista de trámite validada",
  "immig.form.read": "Consulta de la ficha del formulario", "immig.form.save": "Ficha del formulario confirmada",
  "immig.form.pdf": "Borrador del modelo EX descargado", "immig.office.update": "Datos del despacho cambiados",
  "immig.fill.token": "Código para rellenar Mercurio", "immig.fill.read": "Extensión leyó la ficha",
};

export const METODOS_ACCESO: Record<string, string> = {
  demo: "Demostración", local_mfa: "Contraseña + código del móvil", oidc: "Cuenta corporativa (MFA)",
};
export const ESTADOS_SESION: Record<string, string> = {
  activa: "Activa", revocada: "Cerrada", caducada: "Caducada", inactiva: "Cerrada por inactividad",
};

/** Navegador y sistema legibles a partir del user-agent (solo orientativo). */
export function deviceLabel(ua: string | null): string {
  if (!ua) return "Dispositivo desconocido";
  const b = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Navegador";
  const o = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "";
  return o ? `${b} · ${o}` : b;
}

export function label(map: Record<string, string>, key: string): string {
  return map[key] ?? key;
}

export const LEAD_ESTADOS: Record<string, string> = {
  nuevo: "Nuevo", contactado: "Contactado", en_seguimiento: "En seguimiento", cita_solicitada: "Cita solicitada",
  cita_pagada: "Cita pagada", convertido: "Convertido", descartado: "Descartado", no_convertido: "No convertido",
};
export const MATERIAS_LEAD: Record<string, string> = { ...MATERIAS, otra: "Otra" };
export const FASES: Record<string, string> = {
  preapertura: "Preapertura", abierto: "Abierto", en_tramite: "En trámite", suspendido: "Suspendido",
  resuelto: "Resuelto", en_ejecucion: "En ejecución", desistido: "Desistido", archivado: "Archivado",
};
export const FASES_EXT: Record<string, string> = {
  consulta: "Consulta y encargo", documentacion: "Recogida de documentación", preparacion: "Preparación de la solicitud",
  lista_presentar: "Lista para presentar", presentado: "Presentado", requerimiento: "Requerimiento recibido",
  requerimiento_respondido: "Requerimiento respondido", resolucion_favorable: "Resolución favorable",
  resolucion_desfavorable: "Resolución desfavorable", tie: "Tarjeta (TIE) en trámite", recurso: "Impugnación / recurso", cerrado: "Cerrado",
};
export const DOC_ESTADOS: Record<string, string> = { pendiente_revision: "Por revisar", valido: "Válido", rechazado: "No válido", retirado: "Retirado" };
export const ESTADO_REQUISITO: Record<string, string> = { cumplido: "Aportado", falta: "Falta", caducado: "Caducado", por_revisar: "Subido, por revisar" };
export const FAMILIAS_EXT: Record<string, string> = {
  arraigo: "Arraigos", renovacion: "Renovaciones", modificacion: "Modificaciones", reagrupacion: "Reagrupación",
  larga_duracion: "Larga duración", estancia: "Estancias", nacionalidad: "Nacionalidad",
};
export const TAREA_TIPOS: Record<string, string> = {
  gestion: "Gestión", senalamiento: "Señalamiento", conciliacion: "Conciliación", plazo: "Plazo", llamada: "Llamada", otro: "Otro",
};
export const TAREA_ESTADOS: Record<string, string> = {
  pendiente: "Pendiente", en_curso: "En curso", completada: "Completada", pospuesta: "Pospuesta", anulada: "Anulada",
};
export const ACCION_TAREA: Record<string, string> = {
  en_curso: "Empezar", completada: "Completar", pospuesta: "Aplazar", anulada: "Anular",
};
export const ACCION_LEAD: Record<string, string> = {
  contactado: "Marcar contactado", en_seguimiento: "Pasar a seguimiento", cita_solicitada: "Cita solicitada",
  descartado: "Descartar", no_convertido: "No convertido",
};

/** Valor para <input type="datetime-local"> en la hora del navegador (el despacho trabaja en Europe/Madrid). */
export function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
export function fromLocalInput(v: string): string {
  return new Date(v).toISOString();
}
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("es-ES", { timeZone: TIMEZONE, hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}
export function fmtDay(iso: string): string {
  return new Intl.DateTimeFormat("es-ES", { timeZone: TIMEZONE, weekday: "long", day: "numeric", month: "long" }).format(new Date(iso));
}
/** Clave de día (AAAA-MM-DD) en hora de Madrid, para agrupar la agenda. */
export function dayKey(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
  return parts;
}

// ---------------------------------------------------------------- F5.0 economía y gastos
export function fmtMoney(cents: number | null | undefined, currency = "EUR"): string {
  if (cents === null || cents === undefined) return "—";
  return new Intl.NumberFormat("es-ES", { style: "currency", currency }).format(cents / 100);
}
/** "12,50" | "12.50" | "1.234,56" → céntimos. Devuelve null si no es un importe válido. */
export function parseMoney(raw: string): number | null {
  const v = raw.trim().replace(/\s|€/g, "");
  if (!v) return null;
  const norm = v.includes(",") ? v.replace(/\./g, "").replace(",", ".") : v;
  if (!/^\d+(\.\d{1,2})?$/.test(norm)) return null;
  return Math.round(parseFloat(norm) * 100);
}
export function centsToInput(cents: number | null | undefined): string {
  return cents === null || cents === undefined ? "" : (cents / 100).toFixed(2).replace(".", ",");
}
export const METODOS_COBRO: Record<string, string> = {
  efectivo: "Efectivo", tarjeta: "Tarjeta (TPV)", transferencia: "Transferencia", bizum: "Bizum", pasarela: "Pasarela de pago",
};
export const TIPOS_CARGO: Record<string, string> = { honorarios: "Honorarios", gasto_cliente: "Gasto por cuenta del cliente", otro: "Otro" };
export const ESTADOS_COBRO: Record<string, string> = { registrado: "Pendiente de confirmar", confirmado: "Confirmado", anulado: "Anulado" };
export const ESTADOS_DEVOLUCION: Record<string, string> = {
  registrada: "Registrada", en_revision: "En revisión", escalada_legal: "Escalada a letrado", aprobada: "Aprobada",
  rechazada: "Rechazada", pagada: "Pagada",
};
export const ACCION_DEVOLUCION: Record<string, string> = {
  en_revision: "Pasar a revisión", escalada_legal: "Escalar a letrado", aprobada: "Aprobar", rechazada: "Rechazar", pagada: "Registrar pago",
};
export const TIPOS_CAJA: Record<string, string> = {
  cobro: "Cobro", anulacion_cobro: "Anulación de cobro", devolucion: "Devolución", gasto: "Gasto", anulacion_gasto: "Anulación de gasto",
  ingreso_banco: "Ingreso en banco", aportacion: "Aportación", ajuste_arqueo: "Ajuste de arqueo",
};
export const ESTADOS_GASTO: Record<string, string> = {
  borrador: "Borrador (revise y envíe)", enviado: "Enviado a Contabilidad", devuelto: "Devuelto para corregir",
  aprobado: "Aprobado", conciliado: "Conciliado", anulado: "Anulado",
};
export const FORMAS_PAGO_GASTO: Record<string, string> = {
  efectivo_caja: "Efectivo de la caja de la sede", tarjeta_empresa: "Tarjeta de empresa", personal: "Pagado por mí (a reembolsar)",
};

// F5.1 banco y agentes
export const ESTADOS_MOVIMIENTO: Record<string, string> = {
  pendiente: "Pendiente", propuesto: "Propuesta para validar", conciliado: "Conciliado", parcial: "Parcial",
  traspaso: "Traspaso entre cuentas", sin_justificar: "Sin justificar", ignorado: "Ignorado",
};
export const CATEGORIAS_MOVIMIENTO: Record<string, string> = {
  cobro: "Cobro de cliente", tpv: "Liquidación TPV", comision: "Comisión bancaria", bizum: "Bizum", traspaso: "Traspaso",
  devolucion: "Devolución", nomina: "Nómina", seguridad_social: "Seguridad Social", impuestos: "Impuestos",
  alquiler: "Alquiler", proveedor: "Proveedor", otro: "Otro",
};
export const USOS_CUENTA: Record<string, string> = {
  A_laboral: "A · Laboral", B_extranjeria: "B · Extranjería", C_tesoreria: "C · Tesorería", otra: "Otra",
};
export const REGLAS_CONCILIACION: Record<string, string> = {
  referencia: "Referencia del expediente", bizum: "Bizum", tpv: "Liquidación TPV", traspaso: "Traspaso",
  devolucion: "Devolución", importe_fecha: "Importe y fecha (sin referencia)", manual: "Manual",
  factura: "Pago de factura", remesa: "Remesa de proveedores",
};
export const TIPOS_PROPUESTA: Record<string, string> = {
  conciliacion: "Conciliación", excepcion_banco: "Excepción del banco", mensaje: "Mensaje al cliente",
  dato_falta: "Falta un dato", invitar_portal: "Acceso al portal", cierre_caja: "Cierre de caja",
  cierre_pendiente: "Caja sin cerrar", cobro_duplicado: "¿Cobro repetido?", aviso_rrhh: "Aviso de plantilla",
  remesa_firma: "Firma de remesa", factura_validar: "Factura por validar", factura_vence: "Vencimiento",
  factura_falta: "Factura que falta", cierre_mes: "Cierre del mes", informe_revisar: "Informe por revisar",
};
