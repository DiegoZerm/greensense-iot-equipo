import { HttpClient } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Lectura, SerieLecturas } from './modelos';
import { isoLocal } from './tiempo';
import { TiempoRealService } from './tiempo-real.service';

export const HORAS_TENDENCIA = 6;
const VENTANA_MS = HORAS_TENDENCIA * 3_600_000;

/** Lecturas recientes de cada nodo para las gráficas del panel, al día con el flujo SSE. */
@Injectable({ providedIn: 'root' })
export class TendenciasService {
  private readonly http = inject(HttpClient);
  private readonly tiempoReal = inject(TiempoRealService);
  private readonly porNodo = signal<ReadonlyMap<string, readonly Lectura[]>>(new Map());
  private readonly seguidos = new Set<string>();

  constructor() {
    const destruir = inject(DestroyRef);
    this.tiempoReal.eventos.pipe(takeUntilDestroyed(destruir)).subscribe((evento) => {
      if (evento.tipo === 'lectura' && this.seguidos.has(evento.nodo.id)) {
        this.agregar(evento.nodo.id, evento.lectura);
      }
    });
    // Al reconectar se vuelve a cargar lo que se pudo perder mientras tanto.
    this.tiempoReal.abierta.pipe(takeUntilDestroyed(destruir)).subscribe(() => {
      this.seguidos.forEach((id) => this.cargar(id));
    });
  }

  /** Empieza a seguir los nodos que todavía no se siguen. */
  seguir(nodos: readonly string[]): void {
    for (const id of nodos) {
      if (!this.seguidos.has(id)) {
        this.seguidos.add(id);
        this.cargar(id);
      }
    }
  }

  lecturas(nodo: string): readonly Lectura[] {
    return this.porNodo().get(nodo) ?? [];
  }

  private cargar(nodo: string): void {
    const ahora = Date.now();
    const params = {
      nodo,
      desde: isoLocal(new Date(ahora - VENTANA_MS)),
      hasta: isoLocal(new Date(ahora + 60_000)),
    };
    this.http.get<SerieLecturas>('/api/v1/lecturas', { params }).subscribe({
      next: ({ lecturas }) => this.porNodo.update((a) => new Map(a).set(nodo, lecturas)),
      // La gráfica es un complemento: si falla, el panel sigue mostrando los valores.
      error: () => this.porNodo.update((a) => new Map(a).set(nodo, [])),
    });
  }

  private agregar(nodo: string, lectura: Lectura): void {
    this.porNodo.update((actual) => {
      const previas = actual.get(nodo) ?? [];
      const ts = Date.parse(lectura.ts);
      if (previas.some((l) => Date.parse(l.ts) === ts)) {
        return actual;
      }
      // Una lectura reenviada por el nodo puede llegar después de otras más nuevas.
      const limite = Date.now() - VENTANA_MS;
      const lecturas = [...previas, lectura]
        .filter((l) => Date.parse(l.ts) >= limite)
        .sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
      return new Map(actual).set(nodo, lecturas);
    });
  }
}
