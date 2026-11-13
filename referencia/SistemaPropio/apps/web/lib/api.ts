// Cliente de la API. Todas las llamadas pasan por el mismo origen (/api/v1, reescrito
// por Next.js hacia la API), con cookie httpOnly y la cabecera anti-CSRF propia.

export const CSRF_HEADER = { "X-Requested-With": "sistema-propio" };

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string | null;
}

export class ApiError extends Error {
  constructor(public status: number, public body: ApiErrorBody) {
    super(body.message);
  }
}

export function parseError(status: number, payload: unknown): ApiError {
  const e = (payload as { error?: ApiErrorBody } | null)?.error;
  if (e && typeof e.code === "string") return new ApiError(status, e);
  return new ApiError(status, { code: "error", message: "No se ha podido completar la operación." });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...CSRF_HEADER, ...(init.headers as Record<string, string>) };
  if (init.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api/v1${path}`, { ...init, headers, credentials: "same-origin", cache: "no-store" });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = parseError(res.status, data);
    if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      const why = err.body.code.startsWith("sesion_") ? `?error=${encodeURIComponent(err.body.code)}` : "";
      window.location.href = `/login${why}`;
    }
    throw err;
  }
  return data as T;
}

export function fieldErrors(err: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (err instanceof ApiError && Array.isArray(err.body.details)) {
    for (const d of err.body.details as { field?: string; message?: string }[]) {
      if (d.field) out[d.field] = d.message ?? "Valor no válido";
    }
  }
  return out;
}

// ---------------------------------------------------------------- tipos
export interface Page<T> { items: T[]; page: number; page_size: number; total: number }

export interface Me {
  id: string;
  username: string;
  full_name: string;
  email: string;
  auth_mode: string;
  memberships: {
    organization: { id: string; name: string; country: string };
    branch: string | null;
    department: string | null;
    role_code: string;
    role_name: string;
  }[];
  permissions: Record<string, string[]>;
  environment: string;
  has_password: boolean;
}

export interface Organization {
  id: string;
  name: string;
  country: string;
  branches: { id: string; name: string; city: string; kind: string }[];
  can_create_contacts: boolean;
}

export interface ContactMinimal {
  id: string;
  access_level: "minimal" | "full";
  organization_id: string;
  display_name: string;
  primary_branch: string | null;
  phones_masked: string[];
  identifiers_masked: string[];
  possible_duplicate: boolean;
}

export interface ContactFull extends ContactMinimal {
  access_level: "full";
  given_name: string;
  family_names: string;
  birth_date: string | null;
  nationality: string | null;
  preferred_language: string;
  origin: string | null;
  status: string;
  is_synthetic: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  identifiers: { id: string; kind: string; number_normalized: string; country: string; valid_until: string | null }[];
  points: { id: string; kind: string; value_normalized: string; label: string | null; is_primary: boolean }[];
  addresses: { id: string; kind: string; line1: string; line2: string | null; postal_code: string | null;
    municipality: string; province: string | null; country: string }[];
  consents: { purpose: string; granted: boolean; source: string; recorded_at: string }[];
}

export type Contact = ContactMinimal | ContactFull;

export interface CaseMeta {
  id: string;
  organization_id: string;
  last_activity_at: string | null;
  inactive_days: number | null;
  access_level: "metadata" | "full";
  code: string;
  materia: string;
  status: string;
  branch: string;
  department: string;
  contact_id: string;
  contact_name: string | null;
  created_at: string;
}

export interface CaseFull extends CaseMeta {
  title: string;
  confidential_summary: string;
  assignments: { user: string; role: string; since: string; until: string | null }[];
}

export interface AuditEvent {
  id: number;
  occurred_at: string;
  actor_username: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: "ok" | "denied";
  reason: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  hash: string;
}

export function hasPerm(me: Me | null, perm: string): boolean {
  return !!me && Object.values(me.permissions).some((p) => p.includes(perm));
}

// ---------------------------------------------------------------- F1.2 / F2
export interface Lead {
  id: string;
  organization_id: string;
  contact_id: string;
  contact_name: string;
  contact_phone_masked: string | null;
  origin_code: string;
  origin_name: string;
  materia: string;
  branch: string | null;
  summary: string;
  campaign: string | null;
  utm: Record<string, string | null>;
  assigned_user_id: string | null;
  assigned_username: string | null;
  status: string;
  status_changed_at: string;
  created_at: string;
  version: number;
  case_file_id: string | null;
  case_code: string | null;
  case_access: string | null;
  follow_up_level: number;
  allowed_transitions: string[];
}
export interface LeadDetail extends Lead {
  events: { occurred_at: string; actor: string; from_status: string | null; to_status: string; note: string | null }[];
}
export interface Origin { code: string; name: string; requires_campaign: boolean }
export interface Funnel {
  total: number; convertidos: number; conversion: number;
  por_estado: Record<string, number>;
  por_origen: { origin: string; name: string; total: number; convertidos: number; conversion: number }[];
  nota: string;
}

export interface CaseDetail extends CaseFull {
  status_allowed: string[];
  engagement_confirmed_at: string | null;
  phase_events: { at: string; actor: string; from: string | null; to: string; note: string | null }[];
  relations: { id: string; code: string; materia: string; kind: string; note: string | null; access_level: string }[];
  lead_id: string | null;
  can_assign: boolean;
  inactive: boolean;
  assignments: { id: string; user_id: string; user: string; role: string; since: string; until: string | null }[];
}

export interface Task {
  id: string;
  organization_id: string;
  case_id: string | null;
  case_code: string | null;
  contact_name: string | null;
  title: string;
  description: string;
  kind: string;
  priority: string;
  assignee_id: string;
  assignee: string;
  due_at: string;
  start_at: string | null;
  end_at: string | null;
  location: string | null;
  status: string;
  overdue: boolean;
  overlaps: string[];
  legal_deadline: string | null;
  legal_status: string;
  legal_source: string | null;
  legal_validated_by: string | null;
  legal_validated_at: string | null;
  version: number;
  allowed_transitions: string[];
  can_validate_legal: boolean;
  can_edit: boolean;
}
export interface TaskDetail extends Task {
  events: { at: string; actor: string; kind: string; from: string | null; to: string | null;
    old_due_at: string | null; new_due_at: string | null; reason: string | null }[];
}
export interface EligibleUser { id: string; username: string; full_name: string }

export function permsIn(me: Me | null, orgId: string): string[] {
  return me?.permissions[orgId] ?? [];
}

// ---------------------------------------------------------------- F0.2 acceso, sesiones y administración
export interface AuthMode {
  methods: string[]; environment: string; local: boolean; demo: boolean; oidc_configured: boolean; oidc_requested: boolean;
}
export interface SessionInfo {
  id: string; auth_method: string; created_at: string; last_seen_at: string; expires_at: string;
  state: string; ip: string | null; user_agent: string | null; revoke_reason: string | null; current: boolean;
}
export interface AdminMembership {
  id: string; organization_id: string; organization: string; branch_id: string | null; branch: string | null;
  department_id: string | null; department: string | null; role_code: string; role_name: string; status: string;
  valid_from: string; valid_to: string | null; manageable: boolean;
}
export interface AdminUser {
  id: string; username: string; full_name: string; email: string; status: string; is_demo: boolean;
  has_password: boolean; mfa_enrolled: boolean; must_change_password: boolean; last_login_at: string | null;
  created_at: string; memberships: AdminMembership[]; active_sessions: number;
}
export interface AdminUserDetail extends AdminUser { sessions: SessionInfo[] }
export interface TempPassword { user: AdminUser; temporary_password: string; notice: string }
export interface AdminCatalog {
  organizations: { id: string; name: string; country: string; branches: { id: string; name: string; kind: string }[];
    departments: { id: string; name: string; code: string }[] }[];
  roles: { code: string; name: string; description: string; permissions: string[] }[];
}
export interface BackupRun {
  id: string; created_at: string; file_name: string; size_bytes: number | null; sha256: string | null;
  schema_version: string | null; restore_ok: boolean; audit_chain_ok: boolean | null; audit_events: number | null;
  matches_live_chain: boolean | null; table_counts: Record<string, number> | null; detail: string | null; triggered_by: string;
}

/** Una copia solo es válida si se restauró y su auditoría es íntegra y coincide con la base en uso. */
export function backupValid(b: BackupRun): boolean {
  return b.restore_ok && b.audit_chain_ok === true && b.matches_live_chain !== false;
}

// ---------------------------------------------------------------- F5.0 gastos
export interface ExpenseCatalog {
  categories: Record<string, string>;
  organizations: { id: string; name: string; currency: string; branches: { id: string; name: string }[] }[];
  my_cards: { id: string; label: string; organization_id: string }[];
  can_review: boolean; can_read_all: boolean; ocr_available: boolean;
}
export interface ExpenseRow {
  id: string; organization_id: string; status: string; employee: string; employee_id: string; branch: string; branch_id: string;
  expense_date: string | null; supplier_name: string | null; supplier_tax_id: string | null; category: string | null;
  description: string | null; amount_cents: number | null; vat_cents: number | null; currency: string; payment_method: string | null;
  card_id: string | null; card: string | null; has_receipt: boolean; receipt_name: string | null; receipt_mime: string | null;
  review_note: string | null; reviewed_by: string | null; reconcile_ref: string | null; version: number; created_at: string;
}


/** Envío multiparte (subida de archivos) con la misma cabecera anti-CSRF. */
export async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`/api/v1${path}`, { method: "POST", body: form, headers: CSRF_HEADER, credentials: "same-origin" });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw parseError(res.status, data);
  return data as T;
}

// ---------------------------------------------------------------- F5.1 agentes y banco
export interface Proposal {
  id: string; agent: string; agent_name: string; kind: string; title: string; detail: string | null;
  priority: "alta" | "media" | "baja"; status: string; organization_id: string; case_id: string | null;
  case_code: string | null; ref_type: string | null; ref_id: string | null; payload: Record<string, unknown> | null;
  assignee: string | null; created_at: string; decided_by: string | null; decided_at: string | null;
  decision_note: string | null; result: Record<string, unknown> | null; approvable: boolean;
}
