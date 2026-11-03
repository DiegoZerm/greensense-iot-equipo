import { Component, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { catchError, forkJoin, map, of, switchMap, tap } from 'rxjs';
import { mensajeDeError } from '../../core/autenticacion';
import { ConfiguracionService } from '../../core/configuracion.service';
import { HistorialService, Rango, guardarArchivo } from '../../core/historial.service';
import {
  Agregado,
  Cultivo,
  Invernadero,
  Lectura,
  Nodo,
  Resumen,
  VARIABLES,
  Variable,
} from '../../core/modelos';
import { SesionService } from '../../core/sesion.service';
import { formatear, hoyLocal, inicioDelDia, isoLocal, sumarDias } from '../../core/tiempo';
import { GraficaSerie, Punto, RangoReferencia } from '../../shared/grafica-serie';

export type Vista = 'dia' | 'semana' | 'mes';

const DIAS: Record<Vista, number> = { dia: 1, semana: 7, mes: 30 };
const HORA = 3_600_000;

interface Datos {
  clave: string;
  puntos: Record<Variable, Punto[]>;
  pasoMs: number;
  resumen: Resumen;
  recortada: boolean;
}

@Component({
  selector: 'gs-historial',
  imports: [GraficaSerie],
  templateUrl: './historial.html',
  styleUrl: './historial.scss',
})
export class Historial {
  private readonly historial = inject(HistorialService);
  private readonly configuracion = inject(ConfiguracionService);
  private readonly sesion = inject(SesionService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);

  protected readonly vistas: readonly { clave: Vista; nombre: string }[] = [
    { clave: 'dia', nombre: 'Día' },
    { clave: 'semana', nombre: 'Semana' },
    { clave: 'mes', nombre: 'Mes' },
  ];
  protected readonly variables = VARIABLES;
  protected readonly hoy = hoyLocal();
  protected readonly puedeExportar = computed(() => this.sesion.puede('exportar_reportes'));

  // El nodo, la vista y la fecha viven en la URL para poder volver a un día exacto.
  private readonly parametros = toSignal(this.ruta.queryParamMap, {
    initialValue: this.ruta.snapshot.queryParamMap,
  });
  protected readonly vista = computed<Vista>(() => {
    const v = this.parametros().get('vista');
    return v === 'semana' || v === 'mes' ? v : 'dia';
  });
  /** Último día que se muestra (AAAA-MM-DD, hora de México). */
  protected readonly fecha = computed(() => {
    const f = this.parametros().get('fecha');
    return f && /^\d{4}-\d{2}-\d{2}$/.test(f) && f <= this.hoy ? f : this.hoy;
  });

  private readonly catalogos = toSignal(
    forkJoin([
      this.configuracion.nodos(),
      this.configuracion.invernaderos(),
      this.configuracion.cultivos(),
    ]).pipe(
      map(([nodos, invernaderos, cultivos]) => ({ nodos, invernaderos, cultivos })),
      catchError((e) => {
        this.error.set(mensajeDeError(e, 'No se pudieron consultar los nodos'));
        return of({
          nodos: [] as Nodo[],
          invernaderos: [] as Invernadero[],
          cultivos: [] as Cultivo[],
        });
      }),
    ),
  );
  protected readonly nodos = computed(() => this.catalogos()?.nodos ?? []);
  protected readonly nodo = computed(() => {
    const nodos = this.nodos();
    const id = this.parametros().get('nodo');
    return nodos.find((n) => n.id === id) ?? nodos.find((n) => n.activo) ?? nodos[0] ?? null;
  });

  protected readonly rango = computed<Rango | null>(() => {
    const nodo = this.nodo();
    if (!nodo) return null;
    const hasta = inicioDelDia(sumarDias(this.fecha(), 1));
    const desde = inicioDelDia(sumarDias(this.fecha(), 1 - DIAS[this.vista()]));
    return { nodo: nodo.id, desde: isoLocal(desde), hasta: isoLocal(hasta) };
  });
  protected readonly limites = computed(() => {
    const r = this.rango();
    return r ? { desde: Date.parse(r.desde), hasta: Date.parse(r.hasta) } : null;
  });

  protected readonly cargando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly aviso = signal<string | null>(null);

  // Mientras llega la consulta nueva se conserva lo anterior en pantalla.
  protected readonly datos = toSignal(
    toObservable(computed(() => ({ rango: this.rango(), vista: this.vista() }))).pipe(
      switchMap(({ rango, vista }) => {
        if (!rango) return of(null);
        this.cargando.set(true);
        return this.consultar(rango, vista).pipe(
          tap(() => this.error.set(null)),
          catchError((e) => {
            this.error.set(mensajeDeError(e, 'No se pudo consultar el historial'));
            return of(null);
          }),
          tap(() => this.cargando.set(false)),
        );
      }),
    ),
  );

  /** Rango adecuado del cultivo del invernadero del nodo, por variable. */
  protected readonly referencias = computed(() => {
    const catalogos = this.catalogos();
    const nodo = this.nodo();
    const referencias: Partial<Record<Variable, RangoReferencia>> = {};
    if (!catalogos || !nodo) return referencias;
    const invernadero = catalogos.invernaderos.find((i) => i.id === nodo.invernadero_id);
    const cultivo = catalogos.cultivos.find((c) => c.id === invernadero?.cultivo_id);
    for (const u of cultivo?.umbrales ?? []) {
      referencias[u.variable] = { minimo: u.minimo, maximo: u.maximo };
    }
    return referencias;
  });

  /** Las variables que el nodo mide o midió en el periodo. */
  protected readonly visibles = computed(() => {
    const datos = this.datos();
    const nodo = this.nodo();
    return VARIABLES.filter(
      (v) =>
        v.clave !== 'humedad_sustrato' ||
        nodo?.sensor_suelo ||
        (datos?.resumen.variables.humedad_sustrato ?? null) !== null,
    );
  });

  protected readonly titulo = computed(() => {
    const fin = inicioDelDia(this.fecha());
    if (this.vista() === 'dia') {
      return formatear(fin, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    const inicio = inicioDelDia(sumarDias(this.fecha(), 1 - DIAS[this.vista()]));
    const corto: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
    return `${formatear(inicio, corto)} al ${formatear(fin, { ...corto, year: 'numeric' })}`;
  });

  protected cambiar(cambios: { nodo?: string; vista?: Vista; fecha?: string }): void {
    void this.router.navigate([], {
      relativeTo: this.ruta,
      queryParams: {
        nodo: cambios.nodo ?? this.nodo()?.id,
        vista: cambios.vista ?? this.vista(),
        fecha: cambios.fecha ?? this.fecha(),
      },
      replaceUrl: true,
    });
  }

  protected mover(sentido: -1 | 1): void {
    const fecha = sumarDias(this.fecha(), sentido * DIAS[this.vista()]);
    this.cambiar({ fecha: fecha > this.hoy ? this.hoy : fecha });
  }

  protected exportar(tipo: 'lecturas' | 'alertas'): void {
    const rango = this.rango();
    if (!rango) return;
    this.aviso.set(null);
    this.historial.descargar(tipo, rango).subscribe({
      next: guardarArchivo,
      error: (e) => this.aviso.set(mensajeDeError(e, 'No se pudo exportar')),
    });
  }

  protected numero(valor: number, unidad: string): string {
    return `${valor.toLocaleString('es-MX', { maximumFractionDigits: 1 })} ${unidad}`;
  }

  private consultar(rango: Rango, vista: Vista) {
    const clave = `${rango.nodo}|${rango.desde}|${vista}`;
    const resumen = this.historial.resumen(rango);
    if (vista === 'dia') {
      return forkJoin([this.historial.lecturas(rango), resumen]).pipe(
        map(([serie, r]): Datos => ({
          clave,
          puntos: deLecturas(serie.lecturas),
          pasoMs: (this.nodo()?.periodo_s ?? 60) * 1000,
          resumen: r,
          recortada: !serie.completa,
        })),
      );
    }
    const periodo = vista === 'semana' ? 'hora' : 'dia';
    return forkJoin([this.historial.agregadas(rango, periodo), resumen]).pipe(
      map(([agregados, r]): Datos => ({
        clave,
        puntos: deAgregados(agregados),
        pasoMs: periodo === 'hora' ? HORA : 24 * HORA,
        resumen: r,
        recortada: false,
      })),
    );
  }
}

function deLecturas(lecturas: Lectura[]): Record<Variable, Punto[]> {
  const puntos = { temperatura: [], humedad_aire: [], humedad_sustrato: [] } as Record<
    Variable,
    Punto[]
  >;
  for (const l of lecturas) {
    const t = Date.parse(l.ts);
    for (const { clave } of VARIABLES) puntos[clave].push({ t, valor: l[clave] });
  }
  return puntos;
}

function deAgregados(agregados: Agregado[]): Record<Variable, Punto[]> {
  const puntos = { temperatura: [], humedad_aire: [], humedad_sustrato: [] } as Record<
    Variable,
    Punto[]
  >;
  for (const a of agregados) {
    const t = Date.parse(a.inicio);
    for (const { clave } of VARIABLES) {
      const e = a.variables[clave];
      puntos[clave].push({
        t,
        valor: e?.promedio ?? null,
        minimo: e?.minimo ?? null,
        maximo: e?.maximo ?? null,
      });
    }
  }
  return puntos;
}
