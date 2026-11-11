// Fechas en la hora del invernadero. México no tiene horario de verano desde 2022:
// la zona es UTC-6 todo el año, así que los cortes de día se arman con ese desfase.

export const ZONA = 'America/Mexico_City';
const DESFASE = '-06:00';
const DIA_MS = 86_400_000;

/** 'AAAA-MM-DD' de hoy en la hora del invernadero. */
export function hoyLocal(ahora = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(ahora);
}

/** Medianoche local de `fecha` ('AAAA-MM-DD') como Date. */
export function inicioDelDia(fecha: string): Date {
  return new Date(`${fecha}T00:00:00${DESFASE}`);
}

/** Suma días a una fecha 'AAAA-MM-DD'. */
export function sumarDias(fecha: string, dias: number): string {
  const d = new Date(inicioDelDia(fecha).getTime() + dias * DIA_MS);
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(d);
}

/** ISO con el desfase local, como lo espera la API. */
export function isoLocal(fecha: Date): string {
  const local = new Date(fecha.getTime() - 6 * 3_600_000);
  return local.toISOString().slice(0, 19) + DESFASE;
}

const formatos = new Map<string, Intl.DateTimeFormat>();

/** Formatea en la hora del invernadero, con las opciones de Intl.DateTimeFormat. */
export function formatear(fecha: Date | number, opciones: Intl.DateTimeFormatOptions): string {
  const clave = JSON.stringify(opciones);
  let formato = formatos.get(clave);
  if (!formato) {
    formato = new Intl.DateTimeFormat('es-MX', { timeZone: ZONA, ...opciones });
    formatos.set(clave, formato);
  }
  return formato.format(fecha);
}
