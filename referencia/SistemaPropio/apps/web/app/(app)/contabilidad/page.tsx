"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ClosePanel, InvoicesPanel, TreasuryPanel } from "@/components/accounting";
import { ReportsPanel, RoutinePanel } from "@/components/accounting_routine";
import { BankPanel } from "@/components/bank";
import { PendingList } from "@/components/proposals";
import { useMe } from "@/components/session";
import { api, hasPerm } from "@/lib/api";

type Tab = "rutina" | "banco" | "facturas" | "tesoreria" | "cierre" | "informes" | "pendientes";
interface Org { id: string; name: string; branches: { id: string; name: string; kind?: string }[] }

function Contabilidad() {
  const me = useMe();
  const params = useSearchParams();
  const orgsWith = (perm: string) => Object.keys(me.permissions).filter((o) => me.permissions[o].includes(perm));
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [org, setOrg] = useState<string>("");
  useEffect(() => { api<Org[]>("/organizations").then((o) => { setOrgs(o); setOrg((x) => x || (o.find((z) => me.permissions[z.id]?.includes("treasury.read"))?.id ?? o[0]?.id ?? "")); }).catch(() => setOrgs([])); }, [me.permissions]);
  const can = (perm: string) => !!org && (me.permissions[org] ?? []).includes(perm);
  const tabs: [Tab, string, boolean][] = [
    ["rutina", "Rutina de trabajo", orgsWith("accounting.read").length > 0],
    ["banco", "Banco y conciliación", hasPerm(me, "bank.read")],
    ["facturas", "Proveedores y facturas", orgsWith("treasury.read").length > 0],
    ["tesoreria", "Tesorería y remesas", orgsWith("treasury.read").length > 0],
    ["cierre", "Cierre del mes", orgsWith("accounting.read").length > 0],
    ["informes", "Informes", orgsWith("accounting.read").length > 0],
    ["pendientes", "Pendientes de decidir", ["bank.reconcile", "treasury.propose", "treasury.approve", "invoice.validate", "accounting.close"].some((x) => hasPerm(me, x))],
  ];
  const visible = tabs.filter((t) => t[2]);
  const want = params.get("tab") as Tab | null;
  const [tab, setTab] = useState<Tab>(want && visible.some((t) => t[0] === want) ? want : (params.get("mov") ? "banco" : visible[0]?.[0] ?? "banco"));
  const [count, setCount] = useState<Record<string, number>>({});
  if (!visible.length) return <div className="notice notice-warn"><strong>Sin acceso</strong>Su rol no tiene acceso a Contabilidad.</div>;
  const total = Object.values(count).reduce((a, b) => a + b, 0);
  const branches = (orgs.find((o) => o.id === org)?.branches ?? []).filter((b) => !b.kind || b.kind === "sede");
  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Contabilidad</h1>
          <p className="subtitle">Rutina de trabajo, banco y conciliación, facturas de proveedores, tesorería con remesas de doble firma, cierre provisional del mes e informes semanales, quincenales y mensuales. No sustituye la contabilidad de la gestoría. Cobros, devoluciones y cajas siguen en <Link href="/economia">Economía</Link>; gastos de empleados en <Link href="/gastos">Gastos</Link>.</p>
        </div>
        {orgs.length > 1 && tab !== "banco" && tab !== "pendientes" && (
          <select aria-label="Entidad" value={org} onChange={(e) => setOrg(e.target.value)} style={{ width: "auto" }}>
            {orgs.filter((o) => me.permissions[o.id]?.some((p) => p.startsWith("treasury") || p.startsWith("accounting"))).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        )}
      </div>
      <div className="tabs" role="tablist">
        {visible.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{k === "pendientes" && total ? ` (${total})` : ""}</button>)}
      </div>
      {tab === "banco" && <BankPanel />}
      {tab === "facturas" && org && <InvoicesPanel key={org} orgId={org} canRegister={can("invoice.register")} canValidate={can("invoice.validate")} canSuppliers={can("supplier.manage")} branches={branches} />}
      {tab === "tesoreria" && org && <TreasuryPanel key={org} orgId={org} />}
      {tab === "cierre" && org && <ClosePanel key={org} orgId={org} canPrepare={can("accounting.close")} />}
      {tab === "rutina" && org && <RoutinePanel key={org} orgId={org} />}
      {tab === "informes" && org && <ReportsPanel key={org} orgId={org} canGenerate={can("accounting.close")} />}
      <div hidden={tab !== "pendientes"} className="stack">
        {hasPerm(me, "bank.reconcile") && <><h2 style={{ margin: 0 }}>Banco</h2>
          <PendingList params={{ agent: "conciliacion" }} decided onCount={(n) => setCount((c) => ({ ...c, conciliacion: n }))} empty="No hay conciliaciones ni excepciones del banco pendientes." /></>}
        <h2 style={{ margin: 0 }}>Proveedores, remesas, cierre e informes</h2>
        <PendingList params={{ agent: "contabilidad" }} decided onCount={(n) => setCount((c) => ({ ...c, contabilidad: n }))} empty="No hay facturas, firmas de remesas ni cierres pendientes." />
      </div>
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={<p className="muted">Cargando…</p>}><Contabilidad /></Suspense>;
}
