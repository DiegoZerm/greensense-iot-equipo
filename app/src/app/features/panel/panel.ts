import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, DestroyRef, inject } from '@angular/core';
import { EstadoActualService } from '../../core/estado-actual.service';
import { Alerta, EstadoActual, Severidad, VARIABLES, Variable } from '../../core/modelos';

@Component({
  selector: 'gs-panel',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './panel.html',
  styleUrl: './panel.scss',
})
export class Panel {
  protected readonly servicio = inject(EstadoActualService);
  protected readonly variables = VARIABLES;

  constructor() {
    this.servicio.conectar();
    inject(DestroyRef).onDestroy(() => this.servicio.desconectar());
  }

  protected valor(estado: EstadoActual, variable: Variable): number | null {
    return estado.ultima?.[variable] ?? null;
  }

  /** La alerta más grave de la variable decide su color. */
  protected severidad(estado: EstadoActual, variable: Variable): Severidad | 'normal' {
    const deLaVariable = estado.alertas.filter((a) => a.variable === variable);
    if (deLaVariable.some((a) => a.severidad === 'critica')) {
      return 'critica';
    }
    return deLaVariable.length ? 'advertencia' : 'normal';
  }

  /** Alertas que no son de una sola variable, como la desconexión o el riesgo de hongos. */
  protected alertasDelNodo(estado: EstadoActual): Alerta[] {
    return estado.alertas.filter((a) => a.variable === null);
  }

  protected sinSensor(estado: EstadoActual, variable: Variable): boolean {
    return variable === 'humedad_sustrato' && !estado.nodo.sensor_suelo;
  }
}
