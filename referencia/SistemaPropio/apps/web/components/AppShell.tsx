"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, hasPerm, type Me } from "@/lib/api";
import { MODULES } from "@/lib/modules";
import { SessionContext } from "./session";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    api<Me>("/me").then(setMe).catch((e) => setError(e.message));
  }, []);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    window.location.href = "/login";
  }

  if (error) return <div className="login-wrap"><div className="notice notice-danger">{error}</div></div>;
  if (!me) return <div className="login-wrap"><p className="muted">Cargando su sesión…</p></div>;

  const roles = Array.from(new Set(me.memberships.map((m) => m.role_name))).join(" · ");
  const isActive = (slug: string) => (slug === "" ? pathname === "/" : pathname.startsWith(`/${slug}`));

  return (
    <SessionContext.Provider value={me}>
      {me.environment !== "production" && (
        <div className="demo-band" role="status">
          Entorno de {me.environment === "development" ? "DESARROLLO" : me.environment.toUpperCase()}
          {me.auth_mode === "demo" ? " · acceso DEMO" : ""} · solo datos ficticios. No introduzca datos de clientes reales.
        </div>
      )}
      <div className="shell">
        <aside className="sidebar" aria-label="Navegación principal">
          <div className="brand">
            <div className="brand-mark" aria-hidden>SP</div>
            <div>
              <div className="brand-name">SISTEMA PROPIO</div>
              <div className="brand-sub">Despacho · versión F5.6 {me.environment === "production" ? "" : "(demostración)"}</div>
            </div>
          </div>
          <nav className="nav">
            {MODULES.filter((m) => (!m.perm || hasPerm(me, m.perm)) && (!m.anyPerm || m.anyPerm.some((x) => hasPerm(me, x)))).map((m) => (
              <Link key={m.slug} href={`/${m.slug}`} className={isActive(m.slug) ? "active" : undefined}
                aria-current={isActive(m.slug) ? "page" : undefined}>
                <span>{m.label}</span>
                {m.status === "pendiente" && <span className="tag">Pendiente</span>}
                {m.status === "parcial" && <span className="tag" title={m.resumen}>En curso</span>}
              </Link>
            ))}
          </nav>
          <div className="sidebar-foot">
            <div style={{ fontWeight: 600, color: "var(--ink)" }}>{me.full_name}</div>
            <div>{roles}</div>
            <button className="btn btn-sm" style={{ marginTop: 10 }} onClick={logout}>Cerrar sesión</button>
          </div>
        </aside>
        <main className="main">{children}</main>
      </div>
    </SessionContext.Provider>
  );
}
