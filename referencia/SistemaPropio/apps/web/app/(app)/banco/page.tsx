"use client";

// Ruta antigua: el banco vive ahora dentro de Contabilidad.
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

function Go() {
  const router = useRouter();
  const params = useSearchParams();
  useEffect(() => { router.replace(`/contabilidad${params.toString() ? `?${params}` : ""}`); }, [router, params]);
  return <p className="muted">Abriendo Contabilidad…</p>;
}

export default function Page() {
  return <Suspense fallback={null}><Go /></Suspense>;
}
