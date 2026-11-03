import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { mensajeDeError } from '../../core/autenticacion';
import { CambiosUsuario, ConfiguracionService } from '../../core/configuracion.service';
import { ROLES, Rol, Usuario } from '../../core/modelos';
import { SesionService } from '../../core/sesion.service';

@Component({
  selector: 'gs-usuarios',
  imports: [ReactiveFormsModule, DatePipe],
  template: `
    <div class="gs-desplazable">
      <table class="gs-tabla">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Correo</th>
            <th>Rol</th>
            <th>Alta</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (u of usuarios(); track u.id) {
            <tr [attr.data-usuario]="u.id" [class.inactivo]="!u.activo">
              <td>
                {{ u.nombre }}
                @if (u.id === sesion.usuario()?.id) {
                  <small>(tú)</small>
                }
              </td>
              <td>{{ u.correo }}</td>
              <td>
                <select
                  #rol
                  (change)="modificar(u, { rol: $any(rol.value) })"
                  aria-label="Rol"
                  [disabled]="!u.activo"
                >
                  @for (r of roles; track r.clave) {
                    <option [value]="r.clave" [selected]="r.clave === u.rol">{{ r.nombre }}</option>
                  }
                </select>
              </td>
              <td>{{ u.creado_en | date: 'dd/MM/yy' }}</td>
              <td class="acciones">
                <button class="gs-boton secundario" type="button" (click)="restablecer(u)">
                  Nueva contraseña
                </button>
                @if (u.activo) {
                  <button
                    class="gs-boton peligro"
                    type="button"
                    (click)="modificar(u, { activo: false })"
                  >
                    Desactivar
                  </button>
                } @else {
                  <button
                    class="gs-boton secundario"
                    type="button"
                    (click)="modificar(u, { activo: true })"
                  >
                    Activar
                  </button>
                }
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
    <p class="gs-nota">
      Los usuarios no se borran: al desactivarlos pierden el acceso de inmediato y se conserva lo
      que hicieron en la bitácora. Debe quedar al menos un administrador activo.
    </p>

    <h3>Nuevo usuario</h3>
    <form class="gs-form" [formGroup]="formulario" (ngSubmit)="crear()">
      <label>
        Nombre
        <input formControlName="nombre" />
      </label>
      <label>
        Correo
        <input type="email" formControlName="correo" />
      </label>
      <label>
        Rol
        <select formControlName="rol">
          @for (r of roles; track r.clave) {
            <option [value]="r.clave">{{ r.nombre }}</option>
          }
        </select>
      </label>
      <label>
        Contraseña inicial
        <input type="password" formControlName="contrasena" autocomplete="new-password" />
      </label>
      <button class="gs-boton" type="submit" [disabled]="formulario.invalid">Agregar</button>
    </form>
    @if (mensaje(); as m) {
      <p class="gs-aviso" [class.exito]="m.exito" role="status">{{ m.texto }}</p>
    }
  `,
  styles: `
    td select {
      padding: 0.3rem;
      border: 1px solid #ccc;
      border-radius: 6px;
      font: inherit;
    }
    .acciones {
      display: flex;
      gap: 0.4rem;
    }
    small {
      color: #777;
    }
  `,
})
export class Usuarios {
  private readonly configuracion = inject(ConfiguracionService);
  protected readonly sesion = inject(SesionService);

  protected readonly roles = ROLES;
  protected readonly usuarios = signal<Usuario[]>([]);
  protected readonly mensaje = signal<{ texto: string; exito: boolean } | null>(null);
  protected readonly formulario = inject(NonNullableFormBuilder).group({
    nombre: ['', Validators.required],
    correo: ['', [Validators.required, Validators.email]],
    rol: ['operador' as Rol],
    contrasena: ['', [Validators.required, Validators.minLength(8)]],
  });

  constructor() {
    this.cargar();
  }

  protected crear(): void {
    this.configuracion.crearUsuario(this.formulario.getRawValue()).subscribe({
      next: (u) => {
        this.formulario.reset();
        this.avisar(`${u.nombre} puede entrar con ${u.correo}`, true);
        this.cargar();
      },
      error: (e) => this.avisar(mensajeDeError(e), false),
    });
  }

  protected restablecer(usuario: Usuario): void {
    const contrasena = prompt(`Nueva contraseña para ${usuario.nombre} (mínimo 8 caracteres):`);
    if (contrasena) {
      this.modificar(usuario, { contrasena }, 'Contraseña restablecida');
    }
  }

  protected modificar(
    usuario: Usuario,
    cambios: CambiosUsuario,
    exito = 'Cambios guardados',
  ): void {
    this.configuracion.modificarUsuario(usuario.id, cambios).subscribe({
      next: (actualizado) => {
        this.usuarios.update((lista) => lista.map((u) => (u.id === usuario.id ? actualizado : u)));
        this.avisar(exito, true);
        // Si el administrador se cambió el rol a sí mismo, sus permisos cambian ya.
        if (usuario.id === this.sesion.usuario()?.id) {
          void this.sesion.comprobar();
        }
      },
      error: (e) => {
        this.avisar(mensajeDeError(e), false);
        this.cargar();
      },
    });
  }

  private cargar(): void {
    this.configuracion.usuarios().subscribe({
      next: (usuarios) => this.usuarios.set(usuarios),
      error: (e) => this.avisar(mensajeDeError(e), false),
    });
  }

  private avisar(texto: string, exito: boolean): void {
    this.mensaje.set({ texto, exito });
  }
}
