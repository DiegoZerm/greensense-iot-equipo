import { Injectable, InjectionToken, effect, inject, signal, untracked } from '@angular/core';
import { Subject } from 'rxjs';
import { Alerta, Lectura, Nodo } from './modelos';
import { SesionService } from './sesion.service';

/** Permite reemplazar EventSource en las pruebas. */
export const FABRICA_EVENTOS = new InjectionToken<(url: string) => EventSource>('FABRICA_EVENTOS', {
  providedIn: 'root',
  factory: () => (url: string) => new EventSource(url),
});

/** Espera antes de reabrir una conexión que el servidor cerró (por ejemplo, con un 401). */
export const ESPERA_REAPERTURA_MS = new InjectionToken<number>('ESPERA_REAPERTURA_MS', {
  providedIn: 'root',
  factory: () => 5000,
});

export type EventoTiempoReal =
  | { tipo: 'lectura'; nodo: Nodo; lectura: Lectura }
  | { tipo: 'nodo'; nodo: Nodo }
  | { tipo: 'alerta'; alerta: Alerta };

const TIPOS = ['lectura', 'nodo', 'alerta'] as const;
/** EventSource.CLOSED; con el número no depende de que exista EventSource (pruebas). */
const CERRADA = 2;

/**
 * Única conexión SSE con el servidor, compartida por los servicios que la necesitan.
 * Se abre con el primer `conectar()` y se cierra cuando todos llamaron `desconectar()`.
 *
 * EventSource no manda encabezados, así que el token va en la URL. Al cambiar la
 * sesión, la conexión se vuelve a abrir con el token nuevo (o se cierra si no hay).
 */
@Injectable({ providedIn: 'root' })
export class TiempoRealService {
  private readonly crearFuente = inject(FABRICA_EVENTOS);
  private readonly espera = inject(ESPERA_REAPERTURA_MS);
  private readonly sesion = inject(SesionService);
  private fuente: EventSource | null = null;
  private usuarios = 0;
  private reapertura: ReturnType<typeof setTimeout> | null = null;

  readonly eventos = new Subject<EventoTiempoReal>();
  /** Se emite cada vez que la conexión se abre: hay que recargar lo que se pudo perder. */
  readonly abierta = new Subject<void>();
  readonly enVivo = signal(false);

  constructor() {
    effect(() => {
      const token = this.sesion.token();
      untracked(() => this.reabrir(token));
    });
  }

  conectar(): void {
    this.usuarios++;
    if (!this.fuente) {
      this.abrir();
    }
  }

  desconectar(): void {
    this.usuarios = Math.max(0, this.usuarios - 1);
    if (this.usuarios === 0) {
      this.cerrar();
    }
  }

  private abrir(): void {
    const token = this.sesion.token();
    if (!token || this.fuente) {
      return;
    }
    const fuente = this.crearFuente(`/api/v1/eventos?token=${encodeURIComponent(token)}`);
    fuente.addEventListener('open', () => {
      this.enVivo.set(true);
      this.abierta.next();
    });
    fuente.addEventListener('error', () => {
      this.enVivo.set(false);
      // Con un error de red EventSource reintenta solo; con una respuesta de error
      // (401, 403) queda cerrado. Entonces se comprueba la sesión y se reintenta.
      if (fuente.readyState === CERRADA && this.fuente === fuente) {
        this.fuente = null;
        this.programarReapertura();
      }
    });
    for (const tipo of TIPOS) {
      fuente.addEventListener(tipo, (evento) => {
        const datos = JSON.parse((evento as MessageEvent<string>).data);
        this.eventos.next({ tipo, ...datos } as EventoTiempoReal);
      });
    }
    this.fuente = fuente;
  }

  private programarReapertura(): void {
    this.reapertura ??= setTimeout(async () => {
      this.reapertura = null;
      // Si la sesión venció, comprobar() la cierra y el efecto ya no reabre.
      if (this.usuarios > 0 && (await this.sesion.comprobar())) {
        this.abrir();
      }
    }, this.espera);
  }

  private reabrir(token: string | null): void {
    this.cerrar();
    if (token && this.usuarios > 0) {
      this.abrir();
    }
  }

  private cerrar(): void {
    if (this.reapertura) {
      clearTimeout(this.reapertura);
      this.reapertura = null;
    }
    this.fuente?.close();
    this.fuente = null;
    this.enVivo.set(false);
  }
}
