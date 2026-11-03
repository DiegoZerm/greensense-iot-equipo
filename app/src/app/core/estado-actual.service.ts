import { HttpClient } from '@angular/common/http';
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Alerta, EstadoActual } from './modelos';
import { EventoTiempoReal, TiempoRealService } from './tiempo-real.service';

/** Estado actual de cada nodo: se carga una vez y luego se mantiene con el flujo SSE. */
@Injectable({ providedIn: 'root' })
export class EstadoActualService {
  private readonly http = inject(HttpClient);
  private readonly tiempoReal = inject(TiempoRealService);
  private readonly porNodo = signal<ReadonlyMap<string, EstadoActual>>(new Map());

  readonly estados = computed(() =>
    [...this.porNodo().values()].sort(
      (a, b) =>
        a.nodo.invernadero_id.localeCompare(b.nodo.invernadero_id) ||
        a.nodo.id.localeCompare(b.nodo.id),
    ),
  );
  readonly enVivo = this.tiempoReal.enVivo;
  readonly error = signal<string | null>(null);

  constructor() {
    const destruir = inject(DestroyRef);
    this.tiempoReal.eventos.pipe(takeUntilDestroyed(destruir)).subscribe((e) => this.aplicar(e));
    // Al reconectar se carga el estado completo, para no perder lo que pasó mientras tanto.
    this.tiempoReal.abierta.pipe(takeUntilDestroyed(destruir)).subscribe(() => this.cargar());
  }

  conectar(): void {
    this.tiempoReal.conectar();
    this.cargar();
  }

  desconectar(): void {
    this.tiempoReal.desconectar();
  }

  private cargar(): void {
    this.http.get<EstadoActual[]>('/api/v1/lecturas/ultimas').subscribe({
      next: (estados) => {
        this.porNodo.set(new Map(estados.map((e) => [e.nodo.id, e])));
        this.error.set(null);
      },
      error: () => this.error.set('No se pudo consultar el servidor'),
    });
  }

  private aplicar(evento: EventoTiempoReal): void {
    this.porNodo.update((actual) => {
      if (evento.tipo === 'alerta') {
        return this.aplicarAlerta(actual, evento.alerta);
      }
      const previo = actual.get(evento.nodo.id);
      const anterior = previo?.ultima ?? null;
      const lectura = evento.tipo === 'lectura' ? evento.lectura : null;
      // Una lectura reenviada por el nodo puede ser más vieja que la que ya se muestra.
      const ultima = lectura && (!anterior || lectura.ts >= anterior.ts) ? lectura : anterior;
      return new Map(actual).set(evento.nodo.id, {
        nodo: evento.nodo,
        ultima,
        alertas: previo?.alertas ?? [],
      });
    });
  }

  private aplicarAlerta(
    actual: ReadonlyMap<string, EstadoActual>,
    alerta: Alerta,
  ): ReadonlyMap<string, EstadoActual> {
    const estado = actual.get(alerta.nodo_id);
    if (!estado) {
      return actual;
    }
    const otras = estado.alertas.filter((a) => a.id !== alerta.id);
    const alertas = alerta.activa ? [...otras, alerta] : otras;
    return new Map(actual).set(alerta.nodo_id, { ...estado, alertas });
  }
}
