import { HttpClient } from '@angular/common/http';
import { Injectable, effect, inject, signal, untracked } from '@angular/core';
import { SwPush } from '@angular/service-worker';
import { firstValueFrom } from 'rxjs';
import { SesionService } from './sesion.service';

export type EstadoPush =
  | 'cargando'
  | 'no-soportado' // el navegador no tiene service worker o la app corre en modo desarrollo
  | 'no-configurado' // el servidor no tiene claves VAPID
  | 'bloqueado' // el usuario negó el permiso
  | 'inactivo'
  | 'activo';

/**
 * Suscripción del navegador a las notificaciones push de alertas críticas.
 * Cada suscripción es del usuario de la sesión: el servidor solo le manda las alertas
 * que su rol debe recibir.
 */
@Injectable({ providedIn: 'root' })
export class PushService {
  private readonly http = inject(HttpClient);
  private readonly swPush = inject(SwPush);
  private readonly sesion = inject(SesionService);

  readonly estado = signal<EstadoPush>('cargando');
  readonly error = signal<string | null>(null);

  constructor() {
    void this.revisar();
    // Si el navegador ya estaba suscrito (de una sesión anterior), la suscripción pasa
    // al usuario que acaba de entrar.
    effect(() => {
      const usuario = this.sesion.usuario()?.id;
      if (usuario !== undefined) {
        untracked(() => void this.ligarAlUsuario());
      }
    });
  }

  private async ligarAlUsuario(): Promise<void> {
    if (!this.swPush.isEnabled) {
      return;
    }
    const suscripcion = await firstValueFrom(this.swPush.subscription);
    if (suscripcion) {
      await firstValueFrom(
        this.http.post('/api/v1/push/suscripciones', suscripcion.toJSON()),
      ).catch(() => undefined);
    }
  }

  async revisar(): Promise<void> {
    if (!this.swPush.isEnabled) {
      this.estado.set('no-soportado');
      return;
    }
    if (typeof Notification !== 'undefined' && Notification.permission === 'denied') {
      this.estado.set('bloqueado');
      return;
    }
    const suscripcion = await firstValueFrom(this.swPush.subscription);
    this.estado.set(suscripcion ? 'activo' : 'inactivo');
  }

  async activar(): Promise<void> {
    this.error.set(null);
    try {
      const { habilitado, clave } = await firstValueFrom(
        this.http.get<{ habilitado: boolean; clave: string }>('/api/v1/push/clave-publica'),
      );
      if (!habilitado) {
        this.estado.set('no-configurado');
        return;
      }
      const suscripcion = await this.swPush.requestSubscription({ serverPublicKey: clave });
      await firstValueFrom(this.http.post('/api/v1/push/suscripciones', suscripcion.toJSON()));
      this.estado.set('activo');
    } catch {
      if (typeof Notification !== 'undefined' && Notification.permission === 'denied') {
        this.estado.set('bloqueado');
      } else {
        this.error.set('No se pudieron activar las notificaciones');
      }
    }
  }

  async desactivar(): Promise<void> {
    this.error.set(null);
    const suscripcion = await firstValueFrom(this.swPush.subscription);
    if (suscripcion) {
      const endpoint = suscripcion.endpoint;
      await this.swPush.unsubscribe();
      await firstValueFrom(
        this.http.delete('/api/v1/push/suscripciones', { params: { endpoint } }),
      ).catch(() => undefined);
    }
    this.estado.set('inactivo');
  }
}
