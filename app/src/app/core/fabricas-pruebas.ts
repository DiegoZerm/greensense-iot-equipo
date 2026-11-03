// Datos y dobles de prueba compartidos por los specs.
import { Provider, computed, signal } from '@angular/core';
import { Alerta, Lectura, Nodo, Permiso, UsuarioSesion } from './modelos';
import { SesionService } from './sesion.service';

export const nodo = (cambios: Partial<Nodo> = {}): Nodo => ({
  id: 'nodo1',
  invernadero_id: 'inv1',
  nombre: 'Nodo 1',
  sensor_aire: 'DHT22',
  sensor_suelo: true,
  estado: 'conectado',
  firmware: '0.1.0',
  periodo_s: 60,
  ultima_lectura_en: null,
  activo: true,
  ...cambios,
});

export const lectura = (cambios: Partial<Lectura> = {}): Lectura => ({
  ts: '2026-11-01T16:00:00Z',
  arranque: 1,
  seq: 0,
  temperatura: 24.3,
  humedad_aire: 68,
  humedad_sustrato: 52,
  muestras: 5,
  rssi: -60,
  ...cambios,
});

export const alerta = (cambios: Partial<Alerta> = {}): Alerta => ({
  id: 1,
  nodo_id: 'nodo1',
  tipo: 'umbral',
  variable: 'temperatura',
  severidad: 'advertencia',
  mensaje: 'Temperatura cerca del máximo: 27.0 °C (límite 28.0 °C)',
  recomendacion: 'Ventilar o sombrear el invernadero.',
  valor: 27,
  limite: 28,
  iniciada_en: '2026-11-01T16:00:00Z',
  actualizada_en: '2026-11-01T16:00:00Z',
  fuera_desde: null,
  escalada_en: null,
  resuelta_en: null,
  atendida_en: null,
  atendida_por: null,
  atendida_por_nombre: null,
  activa: true,
  ...cambios,
});

/** EventSource falso: las pruebas emiten los eventos a mano. */
export class FuenteFalsa extends EventTarget {
  url = '';
  cerrada = false;
  close(): void {
    this.cerrada = true;
  }
  emitir(tipo: string, datos?: unknown): void {
    this.dispatchEvent(
      datos === undefined
        ? new Event(tipo)
        : new MessageEvent(tipo, { data: JSON.stringify(datos) }),
    );
  }
}

export const usuarioSesion = (
  cambios: Partial<UsuarioSesion> = {},
  permisos: Permiso[] = [
    'ver_panel',
    'notificaciones_cultivo',
    'notificaciones_dispositivo',
    'consultar_historial',
    'atender_alertas',
    'exportar_reportes',
    'gestionar_nodos',
    'configurar_cultivos',
    'administrar_usuarios',
    'consultar_bitacora',
  ],
): UsuarioSesion => ({
  id: 1,
  nombre: 'Ana',
  correo: 'ana@ejemplo.com',
  rol: 'administrador',
  activo: true,
  creado_en: '2026-11-01T16:00:00Z',
  permisos,
  ...cambios,
});

/** SesionService falso: `usuario` en null simula que no hay sesión. */
export function sesionFalsa(usuario: UsuarioSesion | null = usuarioSesion(), token = 'token-1') {
  const usuarioActual = signal(usuario);
  const tokenActual = signal<string | null>(usuario ? token : null);
  return {
    usuario: usuarioActual,
    token: tokenActual,
    iniciada: computed(() => usuarioActual() !== null),
    comprobando: signal(false),
    puede: (permiso: Permiso) => usuarioActual()?.permisos.includes(permiso) ?? false,
    comprobar: vi.fn(async () => usuarioActual() !== null),
    cerrar: vi.fn(() => {
      usuarioActual.set(null);
      tokenActual.set(null);
    }),
    iniciar: vi.fn(),
    expirar: vi.fn(),
  };
}

export type SesionFalsa = ReturnType<typeof sesionFalsa>;

export const proveerSesion = (sesion: SesionFalsa = sesionFalsa()): Provider => ({
  provide: SesionService,
  useValue: sesion,
});
