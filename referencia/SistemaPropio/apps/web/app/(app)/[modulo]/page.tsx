"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { PendingModule } from "@/components/ui";
import { moduleBySlug } from "@/lib/modules";

// Rutas de módulos aún no construidos (CRM, Citas, Agenda…). Las rutas operativas
// (clientes, expedientes, ajustes) tienen su propia página y tienen prioridad.
export default function ModuloPendiente() {
  const { modulo } = useParams<{ modulo: string }>();
  const m = moduleBySlug(modulo);
  if (!m || m.status !== "pendiente") {
    return <div className="notice notice-warn"><strong>Página no encontrada</strong><Link href="/">Volver al inicio</Link></div>;
  }
  return <PendingModule m={m} />;
}
