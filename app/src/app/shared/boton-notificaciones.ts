import { Component, inject } from '@angular/core';
import { PushService } from '../core/push.service';

@Component({
  selector: 'gs-boton-notificaciones',
  template: `
    @switch (push.estado()) {
      @case ('inactivo') {
        <button type="button" (click)="push.activar()">Activar notificaciones</button>
      }
      @case ('activo') {
        <button type="button" class="activo" (click)="push.desactivar()" title="Desactivar">
          Notificaciones activas
        </button>
      }
      @case ('bloqueado') {
        <span title="Permítelas en la configuración del navegador">Notificaciones bloqueadas</span>
      }
      @case ('no-configurado') {
        <span>Notificaciones no configuradas en el servidor</span>
      }
    }
    @if (push.error(); as error) {
      <span class="error" role="alert">{{ error }}</span>
    }
  `,
  styles: `
    :host {
      display: flex;
      gap: 0.5rem;
      align-items: center;
      font-size: 0.8rem;
    }
    button {
      border: 1px solid #fff;
      border-radius: 999px;
      padding: 0.25rem 0.75rem;
      background: transparent;
      color: inherit;
      cursor: pointer;
    }
    button.activo {
      background: rgb(255 255 255 / 20%);
    }
    .error {
      color: #ffcdd2;
    }
  `,
})
export class BotonNotificaciones {
  protected readonly push = inject(PushService);
}
