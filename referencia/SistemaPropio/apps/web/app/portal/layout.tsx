import type { Metadata } from "next";

export const metadata: Metadata = { title: "Portal del cliente", robots: { index: false, follow: false } };

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="portal">
      <header className="portal-head">
        <div className="portal-wrap row" style={{ justifyContent: "space-between" }}>
          <a href="/portal" className="portal-brand">Despacho · Portal del cliente</a>
          <span className="small muted">Conexión segura</span>
        </div>
      </header>
      <main className="portal-wrap">{children}</main>
      <footer className="portal-wrap small muted" style={{ padding: "24px 0" }}>
        Sus mensajes y documentos se guardan cifrados en su expediente. Si tiene una urgencia, llame al despacho.
      </footer>
    </div>
  );
}
