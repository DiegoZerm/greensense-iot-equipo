import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { mensajeDeError } from '../../core/autenticacion';
import { SesionService } from '../../core/sesion.service';

@Component({
  selector: 'gs-login',
  imports: [ReactiveFormsModule],
  template: `
    <form class="tarjeta" [formGroup]="formulario" (ngSubmit)="entrar()">
      <h1>GreenSense IoT</h1>
      <p class="subtitulo">Monitoreo del invernadero</p>
      @if (vencida) {
        <p class="gs-aviso" role="status">Tu sesión terminó. Vuelve a entrar.</p>
      }
      <label>
        Correo
        <input type="email" formControlName="correo" autocomplete="username" required />
      </label>
      <label>
        Contraseña
        <input
          type="password"
          formControlName="contrasena"
          autocomplete="current-password"
          required
        />
      </label>
      @if (error(); as e) {
        <p class="gs-aviso" role="alert">{{ e }}</p>
      }
      <button class="gs-boton" type="submit" [disabled]="formulario.invalid || enviando()">
        {{ enviando() ? 'Entrando…' : 'Entrar' }}
      </button>
    </form>
  `,
  styles: `
    :host {
      display: grid;
      min-height: 80vh;
      place-items: center;
    }
    .tarjeta {
      display: grid;
      gap: 0.75rem;
      width: min(22rem, 100%);
      padding: 1.5rem;
      border: 1px solid #ddd;
      border-radius: 12px;
      background: #fff;
    }
    h1 {
      margin: 0;
      color: var(--gs-verde);
    }
    .subtitulo {
      margin: -0.5rem 0 0.5rem;
      color: #666;
    }
    label {
      display: grid;
      gap: 0.25rem;
      font-size: 0.85rem;
    }
    input {
      padding: 0.5rem;
      border: 1px solid #bbb;
      border-radius: 6px;
      font: inherit;
    }
  `,
})
export class Login {
  private readonly sesion = inject(SesionService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);

  protected readonly formulario = inject(NonNullableFormBuilder).group({
    correo: ['', [Validators.required, Validators.email]],
    contrasena: ['', Validators.required],
  });
  protected readonly enviando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly vencida = this.ruta.snapshot.queryParamMap.get('motivo') === 'vencida';

  protected async entrar(): Promise<void> {
    const { correo, contrasena } = this.formulario.getRawValue();
    this.enviando.set(true);
    this.error.set(null);
    try {
      await this.sesion.iniciar(correo, contrasena);
      const volver = this.ruta.snapshot.queryParamMap.get('volver');
      // Solo rutas internas: evita redirigir a otro sitio con un enlace preparado.
      const destino = volver?.startsWith('/') && !volver.startsWith('//') ? volver : '/';
      await this.router.navigateByUrl(destino);
    } catch (error) {
      this.error.set(mensajeDeError(error, 'No se pudo iniciar sesión'));
    } finally {
      this.enviando.set(false);
    }
  }
}
