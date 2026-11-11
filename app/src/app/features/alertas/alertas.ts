import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap, tap } from 'rxjs';
import { mensajeDeError } from '../../core/autenticacion';
import { AlertasService, FiltroAlertas, LIMITE_CONSULTA } from '../../core/alertas.service';
import { EstadoActualService } from '../../core/estado-actual.service';
import { Alerta, Severidad, TipoAlerta, VARIABLES, Variable } from '../../core/modelos';
import { SesionService } from '../../core/sesion.service';
import { hoyLocal, inicioDelDia, isoLocal, sumarDias } from '../../core/tiempo';

const TIPOS: Record<TipoAlerta, string> = {
  umbral: 'Rango del cultivo',
  hongos: 'Riesgo de hongos',
  sensor: 'Falla de sensor',
  desconexion: 'Nodo desconectado',
};

@Component({
  selector: 'gs-alertas',
  imports: [DatePipe],
  templateUrl: './alertas.html',
  styleUrl: './alertas.scss',
})
export class Alertas {
  private readonly servicio = inject(AlertasService);
  private readonly estadoActual = inject(EstadoActualService);
  private readonly sesion = inject(SesionService);

  protected readonly soloActivas = signal(true);
  protected readonly puedeAtender = computed(() => this.sesion.puede('atender_alertas'));
  protected readonly variables = VARIABLES;
  protected readonly hoy = hoyLocal();

  protected readonly severidad = signal<Severidad | ''>('');
  protected readonly variable = signal<Variable | ''>('');
  /** Días 'AAAA-MM-DD' en la hora del invernadero; los dos se incluyen. */
  protected readonly desde = signal('');
  protected readonly hasta = signal('');
  protected readonly hayFiltros = computed(
    () => !!(this.severidad() || this.variable() || this.desde() || this.hasta()),
  );
  protected readonly rangoInvertido = computed(
    () => !!this.desde() && !!this.hasta() && this.desde() > this.hasta(),
  );

  private readonly filtro = computed<FiltroAlertas | null>(() => {
    if (!this.hayFiltros() || this.rangoInvertido()) return null;
    const filtro: FiltroAlertas = {};
    if (this.severidad()) filtro.severidad = this.severidad() as Severidad;
    if (this.variable()) filtro.variable = this.variable() as Variable;
    if (this.desde()) filtro.desde = isoLocal(inicioDelDia(this.desde()));
    if (this.hasta()) filtro.hasta = isoLocal(inicioDelDia(sumarDias(this.hasta(), 1)));
    return filtro;
  });

  private readonly errorDeConsulta = signal<string | null>(null);
  protected readonly error = computed(() => this.servicio.error() ?? this.errorDeConsulta());

  // La lista normal solo trae las más recientes: lo filtrado se pide al servidor.
  private readonly encontradas = toSignal(
    toObservable(this.filtro).pipe(
      tap(() => this.errorDeConsulta.set(null)),
      switchMap((filtro) =>
        filtro
          ? this.servicio.consultar(filtro).pipe(
              catchError((e) => {
                this.errorDeConsulta.set(mensajeDeError(e, 'No se pudieron filtrar las alertas'));
                return of([] as Alerta[]);
              }),
            )
          : of([] as Alerta[]),
      ),
    ),
    { initialValue: [] as Alerta[] },
  );
  protected readonly recortada = computed(() => this.encontradas().length >= LIMITE_CONSULTA);

  protected readonly visibles = computed(() => {
    // Lo que llega en tiempo real es más nuevo que lo consultado, y también debe filtrarse.
    const porId = new Map(this.encontradas().map((a) => [a.id, a]));
    for (const a of this.servicio.alertas()) porId.set(a.id, a);
    return [...porId.values()]
      .filter((a) => (a.activa || !this.soloActivas()) && this.acepta(a))
      .sort(
        (a, b) =>
          Number(b.activa) - Number(a.activa) ||
          b.iniciada_en.localeCompare(a.iniciada_en) ||
          b.id - a.id,
      );
  });
  private readonly nombres = computed(
    () => new Map(this.estadoActual.estados().map((e) => [e.nodo.id, e.nodo.nombre])),
  );

  constructor() {
    this.servicio.conectar();
    this.estadoActual.conectar();
    inject(DestroyRef).onDestroy(() => {
      this.servicio.desconectar();
      this.estadoActual.desconectar();
    });
  }

  /** Quien filtra busca en el historial: al primer filtro se pasa a "Todas". */
  protected cambiarFiltro(aplicar: () => void): void {
    if (!this.hayFiltros()) this.soloActivas.set(false);
    aplicar();
  }

  protected fijarSeveridad(valor: Severidad | ''): () => void {
    return () => this.severidad.set(valor);
  }

  protected fijarVariable(valor: Variable | ''): () => void {
    return () => this.variable.set(valor);
  }

  protected fijarDesde(valor: string): () => void {
    return () => this.desde.set(valor);
  }

  protected fijarHasta(valor: string): () => void {
    return () => this.hasta.set(valor);
  }

  protected limpiar(): void {
    this.severidad.set('');
    this.variable.set('');
    this.desde.set('');
    this.hasta.set('');
  }

  private acepta(alerta: Alerta): boolean {
    if (this.rangoInvertido()) return false;
    const filtro = this.filtro();
    if (!filtro) return true;
    const inicio = Date.parse(alerta.iniciada_en);
    return (
      (!filtro.severidad || alerta.severidad === filtro.severidad) &&
      (!filtro.variable || alerta.variable === filtro.variable) &&
      (!filtro.desde || inicio >= Date.parse(filtro.desde)) &&
      (!filtro.hasta || inicio < Date.parse(filtro.hasta))
    );
  }

  protected tipo(alerta: Alerta): string {
    return TIPOS[alerta.tipo];
  }

  protected nodo(alerta: Alerta): string {
    return this.nombres().get(alerta.nodo_id) ?? alerta.nodo_id;
  }

  protected atender(alerta: Alerta): void {
    this.servicio.atender(alerta.id).subscribe();
  }
}
