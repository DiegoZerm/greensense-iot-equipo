import { HttpClient } from '@angular/common/http';
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable, tap } from 'rxjs';
import { Alerta } from './modelos';
import { TiempoRealService } from './tiempo-real.service';

/** Historial de alertas, actualizado en tiempo real. */
@Injectable({ providedIn: 'root' })
export class AlertasService {
  private readonly http = inject(HttpClient);
  private readonly tiempoReal = inject(TiempoRealService);
  private readonly porId = signal<ReadonlyMap<number, Alerta>>(new Map());

  /** Activas primero; dentro de cada grupo, las más recientes primero. */
  readonly alertas = computed(() =>
    [...this.porId().values()].sort(
      (a, b) =>
        Number(b.activa) - Number(a.activa) ||
        b.iniciada_en.localeCompare(a.iniciada_en) ||
        b.id - a.id,
    ),
  );
  readonly criticasActivas = computed(
    () => this.alertas().filter((a) => a.activa && a.severidad === 'critica').length,
  );
  readonly error = signal<string | null>(null);

  constructor() {
    const destruir = inject(DestroyRef);
    this.tiempoReal.eventos.pipe(takeUntilDestroyed(destruir)).subscribe((evento) => {
      if (evento.tipo === 'alerta') {
        this.porId.update((actual) => new Map(actual).set(evento.alerta.id, evento.alerta));
      }
    });
    this.tiempoReal.abierta.pipe(takeUntilDestroyed(destruir)).subscribe(() => this.cargar());
  }

  conectar(): void {
    this.tiempoReal.conectar();
    this.cargar();
  }

  desconectar(): void {
    this.tiempoReal.desconectar();
  }

  atender(id: number): Observable<Alerta> {
    return this.http
      .post<Alerta>(`/api/v1/alertas/${id}/atender`, null)
      .pipe(tap((alerta) => this.porId.update((actual) => new Map(actual).set(alerta.id, alerta))));
  }

  private cargar(): void {
    this.http.get<Alerta[]>('/api/v1/alertas', { params: { limite: 200 } }).subscribe({
      next: (alertas) => {
        this.porId.set(new Map(alertas.map((a) => [a.id, a])));
        this.error.set(null);
      },
      error: () => this.error.set('No se pudieron consultar las alertas'),
    });
  }
}
