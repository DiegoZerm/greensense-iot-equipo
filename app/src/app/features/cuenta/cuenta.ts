import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { mensajeDeError } from '../../core/autenticacion';
import { ConfiguracionService } from '../../core/configuracion.service';
import { ROLES } from '../../core/modelos';
import { SesionService } from '../../core/sesion.service';

@Component({
  selector: 'gs-cuenta',
  imports: [ReactiveFormsModule],
  template: `
    <h2>Mi cuenta</h2>
    @if (sesion.usuario(); as usuario) {
      <p>
        {{ usuario.nombre }} · {{ usuario.correo }} · <strong>{{ rol() }}</strong>
      </p>
    }
    <h3>Cambiar contraseña</h3>
    <form class="gs-form" [formGroup]="formulario" (ngSubmit)="cambiar()">
      <label>
        Contraseña actual
        <input type="password" formControlName="actual" autocomplete="current-password" />
      </label>
      <label>
        Nueva (mínimo 8 caracteres)
        <input type="password" formControlName="nueva" autocomplete="new-password" />
      </label>
      <button class="gs-boton" type="submit" [disabled]="formulario.invalid">Cambiar</button>
    </form>
    @if (mensaje(); as m) {
      <p class="gs-aviso" [class.exito]="m.exito" role="status">{{ m.texto }}</p>
    }
  `,
})
export class Cuenta {
  protected readonly sesion = inject(SesionService);
  private readonly configuracion = inject(ConfiguracionService);

  protected readonly formulario = inject(NonNullableFormBuilder).group({
    actual: ['', Validators.required],
    nueva: ['', [Validators.required, Validators.minLength(8)]],
  });
  protected readonly mensaje = signal<{ texto: string; exito: boolean } | null>(null);

  protected rol(): string {
    return ROLES.find((r) => r.clave === this.sesion.usuario()?.rol)?.nombre ?? '';
  }

  protected cambiar(): void {
    const { actual, nueva } = this.formulario.getRawValue();
    this.configuracion.cambiarMiContrasena(actual, nueva).subscribe({
      next: () => {
        this.formulario.reset();
        this.mensaje.set({ texto: 'Contraseña cambiada', exito: true });
      },
      error: (e) => this.mensaje.set({ texto: mensajeDeError(e), exito: false }),
    });
  }
}
