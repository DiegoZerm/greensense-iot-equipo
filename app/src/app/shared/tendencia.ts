import { Component, computed, input, signal } from '@angular/core';
import { formatear } from '../core/tiempo';

export interface PuntoTendencia {
  t: number;
  valor: number;
}

const ANCHO = 1000;
const ALTO = 100;
/** Un hueco mayor a tantos periodos corta la línea: faltaron lecturas. */
const HUECO_EN_PERIODOS = 2.5;

/**
 * Gráfica pequeña de las últimas horas de una variable, sin ejes: el texto de abajo da la
 * ventana, el mínimo y el máximo, o el valor y la hora del punto bajo el puntero. La línea
 * va en el azul de la serie; el estado de la variable lo pinta el renglón del panel.
 */
@Component({
  selector: 'gs-tendencia',
  template: `
    @if (puntos().length) {
      <div
        class="lienzo"
        role="img"
        [attr.aria-label]="nombre() + ': ' + resumen()"
        (pointermove)="mover($event)"
        (pointerleave)="activo.set(null)"
      >
        <svg
          [attr.viewBox]="'0 0 ' + ancho + ' ' + alto"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path class="linea" [attr.d]="linea()" />
        </svg>
        @if (marca(); as m) {
          @if (activo()) {
            <span class="guia" [style.left.%]="m.x"></span>
          }
          <span class="punto" [style.left.%]="m.x" [style.top.%]="m.y"></span>
        }
      </div>
      <small class="pie">{{ texto() }}</small>
    }
  `,
  styles: `
    :host {
      display: block;
    }

    .lienzo {
      position: relative;
      height: 2rem;
      margin: 0.2rem 0 0.1rem;
      touch-action: pan-y;
    }

    svg {
      display: block;
      width: 100%;
      height: 100%;
      overflow: visible;
    }

    .linea {
      fill: none;
      stroke: #2a78d6;
      stroke-width: 2px;
      stroke-linejoin: round;
      stroke-linecap: round;
      vector-effect: non-scaling-stroke;
    }

    .guia {
      position: absolute;
      top: 0;
      bottom: 0;
      width: 1px;
      background: #898781;
    }

    .punto {
      position: absolute;
      width: 8px;
      height: 8px;
      margin: -4px 0 0 -4px;
      border: 2px solid #fff;
      border-radius: 50%;
      box-sizing: content-box;
      background: #2a78d6;
      transform: translate(-2px, -2px);
    }

    .pie {
      display: block;
      color: #52514e;
      font-size: 0.72rem;
      font-weight: 400;
      font-variant-numeric: tabular-nums;
    }
  `,
})
export class Tendencia {
  readonly nombre = input.required<string>();
  readonly unidad = input.required<string>();
  readonly puntos = input.required<readonly PuntoTendencia[]>();
  readonly desde = input.required<number>();
  readonly hasta = input.required<number>();
  readonly periodoMs = input.required<number>();
  readonly horas = input.required<number>();

  protected readonly ancho = ANCHO;
  protected readonly alto = ALTO;
  protected readonly activo = signal<PuntoTendencia | null>(null);

  private readonly escala = computed(() => {
    const valores = this.puntos().map((p) => p.valor);
    let min = Math.min(...valores);
    let max = Math.max(...valores);
    // Una variable casi plana no debe verse como una gran variación.
    if (max - min < 1) {
      const centro = (max + min) / 2;
      min = centro - 0.5;
      max = centro + 0.5;
    }
    return { min, max };
  });

  private x(t: number): number {
    return ((t - this.desde()) / (this.hasta() - this.desde())) * ANCHO;
  }

  private y(valor: number): number {
    const { min, max } = this.escala();
    // Margen para que el trazo no se recorte en los extremos.
    return ALTO - 6 - ((valor - min) / (max - min)) * (ALTO - 12);
  }

  protected readonly linea = computed(() => {
    let d = '';
    let anterior: PuntoTendencia | null = null;
    for (const p of this.puntos()) {
      const corta = !anterior || p.t - anterior.t > this.periodoMs() * HUECO_EN_PERIODOS;
      d += `${corta ? 'M' : 'L'}${this.x(p.t).toFixed(1)},${this.y(p.valor).toFixed(1)}`;
      anterior = p;
    }
    return d;
  });

  /** El punto bajo el puntero o, si no hay, el más reciente. */
  protected readonly marca = computed(() => {
    const p = this.activo() ?? this.puntos().at(-1);
    return p ? { x: (this.x(p.t) / ANCHO) * 100, y: (this.y(p.valor) / ALTO) * 100 } : null;
  });

  protected readonly resumen = computed(() => {
    const valores = this.puntos().map((p) => p.valor);
    const min = this.numero(Math.min(...valores));
    const max = this.numero(Math.max(...valores));
    return `últimas ${this.horas()} h · mín ${min} · máx ${max}`;
  });

  protected readonly texto = computed(() => {
    const p = this.activo();
    if (!p) return this.resumen();
    const hora = formatear(p.t, { hour: '2-digit', minute: '2-digit', hour12: false });
    return `${hora} · ${this.numero(p.valor)}`;
  });

  protected mover(evento: PointerEvent): void {
    const caja = (evento.currentTarget as HTMLElement).getBoundingClientRect();
    const avance = (evento.clientX - caja.left) / caja.width;
    const t = this.desde() + avance * (this.hasta() - this.desde());
    let mejor: PuntoTendencia | null = null;
    for (const p of this.puntos()) {
      if (!mejor || Math.abs(p.t - t) < Math.abs(mejor.t - t)) mejor = p;
    }
    this.activo.set(mejor);
  }

  private numero(valor: number): string {
    return `${valor.toLocaleString('es-MX', { maximumFractionDigits: 1 })} ${this.unidad()}`;
  }
}
