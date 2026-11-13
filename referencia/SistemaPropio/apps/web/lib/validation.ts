// Validación previa en el navegador (comodidad). La validación que cuenta es la del servidor.
const LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE";

export function normalizeDoc(raw: string): string {
  return raw.replace(/[\s.\-]/g, "").toUpperCase();
}

export function checkIdentifier(kind: string, raw: string): string | null {
  const n = normalizeDoc(raw);
  if (!n) return null;
  if (kind === "DNI") {
    const m = /^(\d{8})([A-Z])$/.exec(n);
    if (!m) return "El DNI debe tener 8 dígitos y una letra.";
    return LETTERS[Number(m[1]) % 23] === m[2] ? null : "La letra de control del DNI no es correcta.";
  }
  if (kind === "NIE") {
    const m = /^([XYZ])(\d{7})([A-Z])$/.exec(n);
    if (!m) return "El NIE debe tener el formato X/Y/Z + 7 dígitos + letra.";
    const num = Number(`${"XYZ".indexOf(m[1])}${m[2]}`);
    return LETTERS[num % 23] === m[3] ? null : "La letra de control del NIE no es correcta.";
  }
  if (kind === "PASAPORTE") return /^[A-Z0-9]{5,20}$/.test(n) ? null : "Entre 5 y 20 letras o números.";
  return /^[A-Z0-9-]{3,40}$/.test(n) ? null : "Identificador no válido.";
}

export function checkPhone(raw: string): string | null {
  const digits = raw.replace(/\D/g, "");
  if (!raw.trim()) return null;
  return digits.length >= 9 && digits.length <= 15 ? null : "Revise el teléfono (incluya prefijo si no es español).";
}
