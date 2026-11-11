import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, DestroyRef, effect, inject, signal } from '@angular/core';
import { EstadoActualService } from '../../core/estado-actual.service';
import { Alerta, EstadoActual, Severidad, VARIABLES, Variable } from '../../core/modelos';
import { HORAS_TENDENCIA, TendenciasService } from '../../core/tendencias.service';
import { PuntoTendencia, Tendencia } from '../../shared/tendencia';

@Component({
  selector: 'gs-panel',
  imports: [DatePipe, DecimalPipe, Tendencia],
  templateUrl: './panel.html',
  styleUrl: './panel.scss',
})
export class Panel {
  protected readonly servicio = inject(EstadoActualService);
  private readonly tendencias = inject(TendenciasService);
  protected readonly variables = VARIABLES;
  protected readonly horas = HORAS_TENDENCIA;
  /** La ventana de las gráficas avanza aunque el nodo deje de mandar lecturas. */
  protected readonly ahora = signal(Date.now());

  constructor() {
    this.servicio.conectar();
    effect(() => this.tendencias.seguir(this.servicio.estados().map((e) => e.nodo.id)));
    const reloj = setInterval(() => this.ahora.set(Date.now()), 30_000);
    inject(DestroyRef).onDestroy(() => {
      clearInterval(reloj);
      this.servicio.desconectar();
    });
  }

  protected desde(): number {
    return this.ahora() - HORAS_TENDENCIA * 3_600_000;
  }

  protected tendencia(estado: EstadoActual, variable: Variable): PuntoTendencia[] {
    const puntos: PuntoTendencia[] = [];
    for (const lectura of this.tendencias.lecturas(estado.nodo.id)) {
      const valor = lectura[variable];
      if (valor !== null) puntos.push({ t: Date.parse(lectura.ts), valor });
    }
    return puntos;
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
