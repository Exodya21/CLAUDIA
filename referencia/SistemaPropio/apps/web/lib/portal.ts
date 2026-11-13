// Cliente de la API del portal del cliente: misma cabecera anti-CSRF, sin redirigir al acceso del equipo.
import { ApiError, CSRF_HEADER, parseError } from "@/lib/api";

export async function papi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...CSRF_HEADER, ...(init.headers as Record<string, string>) };
  if (init.body && typeof init.body === "string") headers["Content-Type"] = "application/json";
  const res = await fetch(`/api/v1/portal${path}`, { ...init, headers, credentials: "same-origin", cache: "no-store" });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw parseError(res.status, data);
  return data as T;
}

export function isAuthError(e: unknown): boolean {
  return e instanceof ApiError && e.status === 401;
}

export interface PortalMe { name: string; full_name: string; email: string; needs_terms: boolean; terms: string | null }
export interface PortalCase { code: string; materia: string; stage: string | null; procedure: string | null }
export interface PortalThreadRow {
  id: string; kind: string; case: PortalCase | null; unread: number; urgent_pending: number;
  last_message_at: string | null; missing_documents: number;
}
export interface PortalMsg {
  id: string; kind: string; level: string; text: string; author: { type: string; name: string }; created_at: string;
  edited_at: string | null; requires_confirmation: boolean; confirmed_at: string | null; can_edit: boolean;
  attachments: { id: string; name: string; size: number }[];
}
export interface PortalThread {
  id: string; kind: string; case: PortalCase | null; messages: PortalMsg[];
  missing_documents: { index: number; label: string; required: boolean; state: string }[];
}
