import { Component, effect, inject, untracked } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AlertasService } from './core/alertas.service';
import { ROLES } from './core/modelos';
import { PushService } from './core/push.service';
import { SesionService } from './core/sesion.service';
import { BotonNotificaciones } from './shared/boton-notificaciones';

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive, BotonNotificaciones],
  selector: 'gs-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  protected readonly alertas = inject(AlertasService);
  protected readonly sesion = inject(SesionService);
  private readonly push = inject(PushService);
  private readonly router = inject(Router);

  constructor() {
    // Con sesión se mantiene al día el contador de alertas críticas de la barra.
    effect(() => {
      const iniciada = this.sesion.iniciada();
      untracked(() => (iniciada ? this.alertas.conectar() : this.alertas.desconectar()));
    });
  }

  protected rol(): string {
    const clave = this.sesion.usuario()?.rol;
    return ROLES.find((r) => r.clave === clave)?.nombre ?? '';
  }

  protected configura(): boolean {
    return (
      this.sesion.puede('configurar_cultivos') ||
      this.sesion.puede('gestionar_nodos') ||
      this.sesion.puede('administrar_usuarios')
    );
  }

  protected async salir(): Promise<void> {
    // Este navegador deja de recibir notificaciones: ya no hay nadie en la sesión.
    if (this.push.estado() === 'activo') {
      await this.push.desactivar();
    }
    this.sesion.cerrar();
    await this.router.navigate(['/login']);
  }
}
