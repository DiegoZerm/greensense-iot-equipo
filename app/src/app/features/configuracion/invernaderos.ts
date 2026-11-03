import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { mensajeDeError } from '../../core/autenticacion';
import { ConfiguracionService } from '../../core/configuracion.service';
import { Cultivo, Invernadero } from '../../core/modelos';

@Component({
  selector: 'gs-invernaderos',
  imports: [ReactiveFormsModule],
  template: `
    <div class="gs-desplazable">
      <table class="gs-tabla">
        <thead>
          <tr>
            <th>Id</th>
            <th>Nombre</th>
            <th>Cultivo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (i of invernaderos(); track i.id) {
            <tr [attr.data-invernadero]="i.id">
              <td>{{ i.id }}</td>
              <td>
                <input
                  #nombre
                  [value]="i.nombre"
                  (change)="modificar(i, { nombre: nombre.value })"
                  aria-label="Nombre"
                />
              </td>
              <td>
                <select
                  #cultivo
                  (change)="modificar(i, { cultivo_id: cultivo.value })"
                  aria-label="Cultivo"
                >
                  @for (c of cultivos(); track c.id) {
                    <option [value]="c.id" [selected]="c.id === i.cultivo_id">
                      {{ c.nombre }}
                    </option>
                  }
                </select>
              </td>
              <td>
                <button class="gs-boton peligro" type="button" (click)="borrar(i)">Borrar</button>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>

    <h3>Nuevo invernadero</h3>
    <form class="gs-form" [formGroup]="formulario" (ngSubmit)="crear()">
      <label>
        Id (se usa en los temas MQTT)
        <input formControlName="id" placeholder="invernadero2" />
      </label>
      <label>
        Nombre
        <input formControlName="nombre" />
      </label>
      <label>
        Cultivo
        <select formControlName="cultivo_id">
          @for (c of cultivos(); track c.id) {
            <option [value]="c.id">{{ c.nombre }}</option>
          }
        </select>
      </label>
      <button class="gs-boton" type="submit" [disabled]="formulario.invalid">Agregar</button>
    </form>
    <p class="gs-nota">Un invernadero solo se puede borrar si no tiene nodos.</p>
    @if (mensaje(); as m) {
      <p class="gs-aviso" [class.exito]="m.exito" role="status">{{ m.texto }}</p>
    }
  `,
  styles: `
    td input,
    td select {
      padding: 0.3rem;
      border: 1px solid #ccc;
      border-radius: 6px;
      font: inherit;
    }
  `,
})
export class Invernaderos {
  private readonly configuracion = inject(ConfiguracionService);

  protected readonly invernaderos = signal<Invernadero[]>([]);
  protected readonly cultivos = signal<Cultivo[]>([]);
  protected readonly mensaje = signal<{ texto: string; exito: boolean } | null>(null);
  protected readonly formulario = inject(NonNullableFormBuilder).group({
    id: ['', [Validators.required, Validators.pattern(/^[a-z0-9-]{1,32}$/)]],
    nombre: ['', Validators.required],
    cultivo_id: ['hortalizas-hoja', Validators.required],
  });

  constructor() {
    this.cargar();
  }

  protected crear(): void {
    this.configuracion.crearInvernadero(this.formulario.getRawValue()).subscribe({
      next: (i) => {
        this.formulario.reset();
        this.avisar(`Invernadero ${i.id} agregado`, true);
        this.cargar();
      },
      error: (e) => this.avisar(mensajeDeError(e), false),
    });
  }

  protected modificar(invernadero: Invernadero, cambios: Partial<Invernadero>): void {
    this.configuracion.modificarInvernadero(invernadero.id, cambios).subscribe({
      next: () => this.avisar('Cambios guardados', true),
      error: (e) => {
        this.avisar(mensajeDeError(e), false);
        this.cargar();
      },
    });
  }

  protected borrar(invernadero: Invernadero): void {
    if (!confirm(`¿Borrar el invernadero ${invernadero.nombre}?`)) {
      return;
    }
    this.configuracion.borrarInvernadero(invernadero.id).subscribe({
      next: () => this.cargar(),
      error: (e) => this.avisar(mensajeDeError(e), false),
    });
  }

  private cargar(): void {
    forkJoin([this.configuracion.invernaderos(), this.configuracion.cultivos()]).subscribe({
      next: ([invernaderos, cultivos]) => {
        this.invernaderos.set(invernaderos);
        this.cultivos.set(cultivos);
      },
      error: (e) => this.avisar(mensajeDeError(e), false),
    });
  }

  private avisar(texto: string, exito: boolean): void {
    this.mensaje.set({ texto, exito });
  }
}
