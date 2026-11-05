import { DatePipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { AlertasService } from '../../core/alertas.service';
import { EstadoActualService } from '../../core/estado-actual.service';
import { Alerta, TipoAlerta } from '../../core/modelos';
import { SesionService } from '../../core/sesion.service';

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
  protected readonly error = this.servicio.error;
  protected readonly visibles = computed(() =>
    this.servicio.alertas().filter((a) => a.activa || !this.soloActivas()),
  );
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
