import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { Permiso, UsuarioSesion } from './modelos';

const CLAVE_TOKEN = 'greensense.token';

/** Sesión del usuario: token JWT guardado en el navegador y sus permisos. */
@Injectable({ providedIn: 'root' })
export class SesionService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly token = signal<string | null>(leerToken());
  readonly usuario = signal<UsuarioSesion | null>(null);
  readonly iniciada = computed(() => this.usuario() !== null);
  /** Mientras se comprueba un token guardado al abrir la app. */
  readonly comprobando = signal(false);

  private comprobacion: Promise<boolean> | null = null;

  puede(permiso: Permiso): boolean {
    return this.usuario()?.permisos.includes(permiso) ?? false;
  }

  async iniciar(correo: string, contrasena: string): Promise<void> {
    const sesion = await firstValueFrom(
      this.http.post<{ token: string; usuario: UsuarioSesion }>('/api/v1/auth/login', {
        correo,
        contrasena,
      }),
    );
    guardarToken(sesion.token);
    this.token.set(sesion.token);
    this.usuario.set(sesion.usuario);
  }

  /**
   * Comprueba con el servidor el token guardado (al abrir la app o tras perder la
   * conexión). Devuelve si hay sesión. Varias llamadas a la vez comparten la consulta.
   */
  comprobar(): Promise<boolean> {
    if (!this.token()) {
      return Promise.resolve(false);
    }
    this.comprobacion ??= (async () => {
      this.comprobando.set(true);
      try {
        this.usuario.set(await firstValueFrom(this.http.get<UsuarioSesion>('/api/v1/auth/yo')));
        return true;
      } catch {
        // Si fue un 401, el interceptor ya cerró la sesión.
        return this.iniciada();
      } finally {
        this.comprobando.set(false);
        this.comprobacion = null;
      }
    })();
    return this.comprobacion;
  }

  cerrar(): void {
    guardarToken(null);
    this.token.set(null);
    this.usuario.set(null);
  }

  /** El servidor rechazó el token (venció o desactivaron al usuario). */
  expirar(): void {
    if (!this.token()) {
      return;
    }
    this.cerrar();
    void this.router.navigate(['/login'], { queryParams: { motivo: 'vencida' } });
  }
}

function leerToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_TOKEN);
  } catch {
    return null;
  }
}

function guardarToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(CLAVE_TOKEN, token);
    } else {
      localStorage.removeItem(CLAVE_TOKEN);
    }
  } catch {
    // Sin almacenamiento (modo privado estricto): la sesión dura lo que la pestaña.
  }
}
