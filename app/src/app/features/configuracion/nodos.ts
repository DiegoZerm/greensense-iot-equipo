import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { mensajeDeError } from '../../core/autenticacion';
import { CambiosNodo, ConfiguracionService } from '../../core/configuracion.service';
import { Invernadero, Nodo } from '../../core/modelos';

@Component({
  selector: 'gs-nodos',
  imports: [ReactiveFormsModule, DatePipe],
  template: `
    <div class="gs-desplazable">
      <table class="gs-tabla">
        <thead>
          <tr>
            <th>Nodo</th>
            <th>Nombre</th>
            <th>Sensor del aire</th>
            <th>Suelo</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (n of nodos(); track n.id) {
            <tr [attr.data-nodo]="n.id" [class.inactivo]="!n.activo">
              <td>
                {{ n.invernadero_id }}/<strong>{{ n.id }}</strong>
              </td>
              <td>
                <input
                  #nombre
                  [value]="n.nombre"
                  (change)="modificar(n, { nombre: nombre.value })"
                  aria-label="Nombre"
                />
              </td>
              <td>
                <select
                  #sensor
                  (change)="modificar(n, { sensor_aire: sensor.value })"
                  aria-label="Sensor del aire"
                >
                  @for (s of sensores; track s) {
                    <option [value]="s" [selected]="s === n.sensor_aire">{{ s }}</option>
                  }
                </select>
              </td>
              <td>
                <input
                  #suelo
                  type="checkbox"
                  [checked]="n.sensor_suelo"
                  (change)="modificar(n, { sensor_suelo: suelo.checked })"
                  aria-label="Tiene sensor de suelo"
                />
              </td>
              <td>
                @if (!n.activo) {
                  De baja
                } @else {
                  {{ n.estado }}
                  @if (n.firmware) {
                    <small>· v{{ n.firmware }}</small>
                  }
                  @if (n.ultima_lectura_en) {
                    <small>· {{ n.ultima_lectura_en | date: 'dd/MM HH:mm' }}</small>
                  }
                }
              </td>
              <td>
                @if (n.activo) {
                  <button class="gs-boton peligro" type="button" (click)="darDeBaja(n)">
                    Dar de baja
                  </button>
                } @else {
                  <button
                    class="gs-boton secundario"
                    type="button"
                    (click)="modificar(n, { activo: true })"
                  >
                    Reactivar
                  </button>
                }
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="6">No hay nodos registrados.</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
    <p class="gs-nota">
      El nodo informa su sensor y su firmware al conectarse, y eso reemplaza lo que se configure
      aquí. Un nodo dado de baja conserva su historial, pero el servidor ignora sus lecturas y no
      genera alertas.
    </p>

    <h3>Registrar nodo</h3>
    <form class="gs-form" [formGroup]="formulario" (ngSubmit)="crear()">
      <label>
        Invernadero
        <select formControlName="invernadero_id">
          @for (i of invernaderos(); track i.id) {
            <option [value]="i.id">{{ i.nombre }}</option>
          }
        </select>
      </label>
      <label>
        Id (usuario MQTT del nodo)
        <input formControlName="id" placeholder="nodo3" />
      </label>
      <label>
        Nombre
        <input formControlName="nombre" placeholder="Junto a la puerta" />
      </label>
      <label>
        Sensor del aire
        <select formControlName="sensor_aire">
          @for (s of sensores; track s) {
            <option [value]="s">{{ s }}</option>
          }
        </select>
      </label>
      <label class="casilla">
        <input type="checkbox" formControlName="sensor_suelo" /> Sensor de suelo
      </label>
      <button class="gs-boton" type="submit" [disabled]="formulario.invalid">Registrar</button>
    </form>
    <p class="gs-nota">
      Además hay que darle su usuario MQTT: agregarlo a <code>MQTT_NODOS</code> en
      <code>infra/.env</code> y correr <code>infra/mosquitto/crear_usuarios.sh</code>.
    </p>
    @if (mensaje(); as m) {
      <p class="gs-aviso" [class.exito]="m.exito" role="status">{{ m.texto }}</p>
    }
  `,
  styles: `
    td input:not([type='checkbox']),
    td select {
      padding: 0.3rem;
      border: 1px solid #ccc;
      border-radius: 6px;
      font: inherit;
    }
    .casilla {
      display: flex !important;
      gap: 0.3rem;
      align-items: center;
    }
    small {
      color: #777;
    }
  `,
})
export class Nodos {
  private readonly configuracion = inject(ConfiguracionService);

  protected readonly sensores = ['DHT11', 'DHT22'];
  protected readonly nodos = signal<Nodo[]>([]);
  protected readonly invernaderos = signal<Invernadero[]>([]);
  protected readonly mensaje = signal<{ texto: string; exito: boolean } | null>(null);
  protected readonly formulario = inject(NonNullableFormBuilder).group({
    invernadero_id: ['', Validators.required],
    id: ['', [Validators.required, Validators.pattern(/^[a-z0-9-]{1,32}$/)]],
    nombre: ['', Validators.required],
    sensor_aire: ['DHT22'],
    sensor_suelo: [false],
  });

  constructor() {
    this.cargar();
  }

  protected crear(): void {
    this.configuracion.crearNodo(this.formulario.getRawValue()).subscribe({
      next: (nodo) => {
        this.formulario.reset({ invernadero_id: nodo.invernadero_id });
        this.avisar(`Nodo ${nodo.id} registrado`, true);
        this.cargar();
      },
      error: (e) => this.avisar(mensajeDeError(e), false),
    });
  }

  protected darDeBaja(nodo: Nodo): void {
    if (confirm(`¿Dar de baja ${nodo.nombre}? Sus alertas activas se cerrarán.`)) {
      this.modificar(nodo, { activo: false });
    }
  }

  protected modificar(nodo: Nodo, cambios: CambiosNodo): void {
    this.configuracion.modificarNodo(nodo.id, cambios).subscribe({
      next: (actualizado) => {
        this.nodos.update((nodos) => nodos.map((n) => (n.id === nodo.id ? actualizado : n)));
        this.avisar('Cambios guardados', true);
      },
      error: (e) => {
        this.avisar(mensajeDeError(e), false);
        this.cargar();
      },
    });
  }

  private cargar(): void {
    forkJoin([this.configuracion.nodos(), this.configuracion.invernaderos()]).subscribe({
      next: ([nodos, invernaderos]) => {
        this.nodos.set(nodos);
        this.invernaderos.set(invernaderos);
        if (!this.formulario.controls.invernadero_id.value && invernaderos[0]) {
          this.formulario.controls.invernadero_id.setValue(invernaderos[0].id);
        }
      },
      error: (e) => this.avisar(mensajeDeError(e), false),
    });
  }

  private avisar(texto: string, exito: boolean): void {
    this.mensaje.set({ texto, exito });
  }
}
