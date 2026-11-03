import {
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { formatear } from '../core/tiempo';

/** Un punto de la serie. Con `minimo` y `maximo` se dibuja la banda de un agregado. */
export interface Punto {
  t: number;
  valor: number | null;
  minimo?: number | null;
  maximo?: number | null;
}

export interface RangoReferencia {
  minimo: number;
  maximo: number;
}

// El lienzo mide lo mismo que el espacio disponible (en px), para que el texto de los ejes
// conserve su tamaño en un teléfono. 720 es solo el ancho antes de medir.
const ANCHO_INICIAL = 720;
const ANCHO_MINIMO = 240;
const M = { arriba: 12, derecha: 12, abajo: 26, izquierda: 44 };
/** Espacio mínimo para cada etiqueta del eje horizontal ("00:00", "3 nov"). */
const SEPARACION_ETIQUETAS = 56;
/** La altura crece con el ancho, de 200 px en un teléfono a 300 px en escritorio. */
const ALTO_MINIMO = 200;
const ALTO_MAXIMO = 300;
const HORA = 3_600_000;
const DIA = 24 * HORA;

/**
 * Serie de tiempo de una variable: línea de 2 px, banda de mínimo a máximo cuando los
 * puntos son agregados, franja gris con el rango adecuado del cultivo y cortes donde
 * faltan lecturas. Al pasar el puntero muestra el valor; la tabla da los mismos datos
 * sin depender del puntero.
 */
@Component({
  selector: 'gs-grafica-serie',
  templateUrl: './grafica-serie.html',
  styleUrl: './grafica-serie.scss',
})
export class GraficaSerie {
  readonly titulo = input.required<string>();
  readonly unidad = input.required<string>();
  readonly puntos = input.required<readonly Punto[]>();
  readonly desde = input.required<number>();
  readonly hasta = input.required<number>();
  /** Separación normal entre puntos; un hueco mayor corta la línea. */
  readonly pasoMs = input.required<number>();
  readonly rango = input<RangoReferencia | null>(null);

  protected readonly ancho = signal(ANCHO_INICIAL);
  protected readonly alto = computed(() =>
    Math.round(Math.min(ALTO_MAXIMO, Math.max(ALTO_MINIMO, this.ancho() * 0.28))),
  );
  protected readonly m = M;
  protected readonly plotAncho = computed(() => this.ancho() - M.izquierda - M.derecha);
  protected readonly plotAlto = computed(() => this.alto() - M.arriba - M.abajo);

  private readonly lienzo = viewChild.required<ElementRef<HTMLElement>>('lienzo');

  constructor() {
    const destruir = inject(DestroyRef);
    afterNextRender(() => {
      if (typeof ResizeObserver === 'undefined') return;
      const observador = new ResizeObserver(([entrada]) => {
        const ancho = Math.round(entrada.contentRect.width);
        if (ancho > 0) this.ancho.set(Math.max(ANCHO_MINIMO, ancho));
      });
      observador.observe(this.lienzo().nativeElement);
      destruir.onDestroy(() => observador.disconnect());
    });
  }

  protected readonly conDatos = computed(() => this.puntos().some((p) => p.valor !== null));
  protected readonly agregados = computed(() => this.puntos().some((p) => p.minimo != null));
  protected readonly verTabla = signal(false);
  private readonly activo = signal<number | null>(null);

  /** Dominio vertical con números redondos, incluido el rango de referencia. */
  protected readonly escalaY = computed(() => {
    const valores: number[] = [];
    for (const p of this.puntos()) {
      for (const v of [p.valor, p.minimo, p.maximo]) {
        if (v != null) valores.push(v);
      }
    }
    const rango = this.rango();
    if (rango) valores.push(rango.minimo, rango.maximo);
    if (!valores.length) return { min: 0, max: 1, ticks: [0, 1] };
    let min = Math.min(...valores);
    let max = Math.max(...valores);
    if (max - min < 1) {
      min -= 0.5;
      max += 0.5;
    }
    const paso = pasoRedondo((max - min) / 4);
    min = Math.floor(min / paso) * paso;
    max = Math.ceil(max / paso) * paso;
    const ticks: number[] = [];
    for (let v = min; v <= max + paso / 2; v += paso) ticks.push(redondear(v));
    return { min, max, ticks };
  });

  protected x(t: number): number {
    const span = this.hasta() - this.desde();
    return M.izquierda + ((t - this.desde()) / span) * this.plotAncho();
  }

  protected y(v: number): number {
    const { min, max } = this.escalaY();
    return M.arriba + (1 - (v - min) / (max - min)) * this.plotAlto();
  }

  /** Tramos continuos: se cortan en valores nulos y en huecos de más de 2.5 pasos. */
  private readonly tramos = computed(() => {
    const tramos: Punto[][] = [];
    let actual: Punto[] = [];
    let anterior: Punto | null = null;
    for (const p of this.puntos()) {
      const hueco = anterior && p.t - anterior.t > this.pasoMs() * 2.5;
      if (p.valor === null || hueco) {
        if (actual.length) tramos.push(actual);
        actual = [];
      }
      if (p.valor !== null) actual.push(p);
      anterior = p;
    }
    if (actual.length) tramos.push(actual);
    return tramos;
  });

  protected readonly linea = computed(() =>
    this.tramos()
      .filter((t) => t.length > 1)
      .map((t) =>
        t.map((p, i) => `${i ? 'L' : 'M'}${f(this.x(p.t))},${f(this.y(p.valor!))}`).join(''),
      )
      .join(''),
  );

  /** Puntos sueltos (sin vecinos) se dibujan como marcador para que no desaparezcan. */
  protected readonly sueltos = computed(() =>
    this.tramos()
      .filter((t) => t.length === 1)
      .map(([p]) => ({ cx: this.x(p.t), cy: this.y(p.valor!) })),
  );

  protected readonly banda = computed(() =>
    this.tramos()
      .filter((t) => t.length > 1 && t.every((p) => p.minimo != null && p.maximo != null))
      .map((t) => {
        const arriba = t.map((p, i) => `${i ? 'L' : 'M'}${f(this.x(p.t))},${f(this.y(p.maximo!))}`);
        const abajo = [...t].reverse().map((p) => `L${f(this.x(p.t))},${f(this.y(p.minimo!))}`);
        return [...arriba, ...abajo, 'Z'].join('');
      })
      .join(''),
  );

  protected readonly franja = computed(() => {
    const rango = this.rango();
    if (!rango) return null;
    const arriba = this.y(rango.maximo);
    return { y: arriba, alto: this.y(rango.minimo) - arriba };
  });

  protected readonly ticksX = computed(() => {
    const desde = this.desde();
    const span = this.hasta() - desde;
    let paso = span <= 1.5 * DIA ? 3 * HORA : span <= 10 * DIA ? DIA : 5 * DIA;
    // En pantallas angostas se salta etiquetas para que no se encimen.
    while ((this.plotAncho() * paso) / span < SEPARACION_ETIQUETAS && paso < span) paso *= 2;
    const formato: Intl.DateTimeFormatOptions =
      paso < DIA
        ? { hour: '2-digit', minute: '2-digit', hour12: false }
        : { day: 'numeric', month: 'short' };
    const ticks = [];
    // El final del rango no lleva etiqueta: es el inicio del día siguiente y no cabría.
    for (let t = desde; t < this.hasta(); t += paso) {
      ticks.push({ x: this.x(t), texto: formatear(t, formato) });
    }
    return ticks;
  });

  protected readonly punto = computed(() => {
    const i = this.activo();
    const p = i === null ? null : this.puntos()[i];
    if (!p || p.valor === null) return null;
    return {
      cx: this.x(p.t),
      cy: this.y(p.valor),
      izquierda: (this.x(p.t) / this.ancho()) * 100,
      alLado: this.x(p.t) > this.ancho() * 0.65,
      valor: this.numero(p.valor),
      cuando: this.cuando(p.t),
      extremos:
        p.minimo != null && p.maximo != null
          ? `mín ${this.numero(p.minimo)} · máx ${this.numero(p.maximo)}`
          : null,
    };
  });

  protected mover(evento: PointerEvent): void {
    const svg = evento.currentTarget as SVGSVGElement;
    const caja = svg.getBoundingClientRect();
    const xVista = ((evento.clientX - caja.left) / caja.width) * this.ancho();
    const avance = (xVista - M.izquierda) / this.plotAncho();
    const t = this.desde() + avance * (this.hasta() - this.desde());
    this.activo.set(masCercano(this.puntos(), t));
  }

  protected salir(): void {
    this.activo.set(null);
  }

  protected numero(v: number): string {
    return `${v.toLocaleString('es-MX', { maximumFractionDigits: 1 })} ${this.unidad()}`;
  }

  protected cuando(t: number): string {
    const agregado = this.agregados();
    const span = this.hasta() - this.desde();
    if (agregado && span > 10 * DIA) {
      return formatear(t, { weekday: 'short', day: 'numeric', month: 'short' });
    }
    if (agregado) {
      return `${formatear(t, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })} (1 h)`;
    }
    return formatear(t, {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }

  protected readonly filasTabla = computed(() =>
    this.puntos()
      .filter((p) => p.valor !== null)
      .map((p) => ({
        cuando: this.cuando(p.t),
        valor: this.numero(p.valor!),
        minimo: p.minimo != null ? this.numero(p.minimo) : '',
        maximo: p.maximo != null ? this.numero(p.maximo) : '',
      })),
  );
}

function f(n: number): string {
  return n.toFixed(1);
}

function redondear(v: number): number {
  return Math.round(v * 1000) / 1000;
}

/** 1, 2, 2.5 o 5 por una potencia de 10. */
function pasoRedondo(bruto: number): number {
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const n = bruto / potencia;
  const factor = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return factor * potencia;
}

/** Índice del punto con valor más cercano a `t` (los puntos vienen en orden). */
export function masCercano(puntos: readonly Punto[], t: number): number | null {
  let mejor: number | null = null;
  let distancia = Infinity;
  let bajo = 0;
  let alto = puntos.length - 1;
  while (bajo < alto) {
    const medio = (bajo + alto) >> 1;
    if (puntos[medio].t < t) bajo = medio + 1;
    else alto = medio;
  }
  // Revisa alrededor por si los vecinos inmediatos no tienen valor.
  for (let i = Math.max(0, bajo - 3); i <= Math.min(puntos.length - 1, bajo + 3); i++) {
    if (puntos[i].valor === null) continue;
    const d = Math.abs(puntos[i].t - t);
    if (d < distancia) {
      distancia = d;
      mejor = i;
    }
  }
  return mejor;
}
