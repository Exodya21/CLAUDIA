import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SISTEMA PROPIO",
  description: "Plataforma jurídica y empresarial del despacho — entorno de desarrollo con datos ficticios",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
