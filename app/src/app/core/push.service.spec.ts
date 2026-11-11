import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { SwPush } from '@angular/service-worker';
import { BehaviorSubject } from 'rxjs';
import { SesionFalsa, proveerSesion, sesionFalsa, usuarioSesion } from './fabricas-pruebas';
import { PushService } from './push.service';

const SUSCRIPCION = {
  endpoint: 'https://push.ejemplo/abc',
  toJSON: () => ({ endpoint: 'https://push.ejemplo/abc', keys: { p256dh: 'k', auth: 'a' } }),
} as unknown as PushSubscription;

function crear(
  habilitadoEnNavegador: boolean,
  suscripcionInicial: PushSubscription | null,
  sesion: SesionFalsa = sesionFalsa(null),
) {
  const suscripcion = new BehaviorSubject<PushSubscription | null>(suscripcionInicial);
  const swPush = {
    isEnabled: habilitadoEnNavegador,
    subscription: suscripcion,
    requestSubscription: vi.fn(async () => {
      suscripcion.next(SUSCRIPCION);
      return SUSCRIPCION;
    }),
    unsubscribe: vi.fn(async () => suscripcion.next(null)),
  };
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: SwPush, useValue: swPush },
      proveerSesion(sesion),
    ],
  });
  return {
    servicio: TestBed.inject(PushService),
    http: TestBed.inject(HttpTestingController),
    swPush,
  };
}

/** Deja correr las promesas pendientes. */
const esperar = () => new Promise((r) => setTimeout(r));

describe('PushService', () => {
  it('sin service worker no se puede usar', async () => {
    const { servicio } = crear(false, null);
    await esperar();
    expect(servicio.estado()).toBe('no-soportado');
  });

  it('detecta una suscripción existente', async () => {
    const { servicio } = crear(true, SUSCRIPCION);
    await esperar();
    expect(servicio.estado()).toBe('activo');
  });

  it('activar pide la clave, suscribe al navegador y registra en el servidor', async () => {
    const { servicio, http, swPush } = crear(true, null);
    await esperar();
    expect(servicio.estado()).toBe('inactivo');

    const activando = servicio.activar();
    http.expectOne('/api/v1/push/clave-publica').flush({ habilitado: true, clave: 'CLAVE' });
    await esperar();
    const registro = http.expectOne({ method: 'POST', url: '/api/v1/push/suscripciones' });
    expect(registro.request.body).toEqual(SUSCRIPCION.toJSON());
    registro.flush({ id: 1 });
    await activando;

    expect(swPush.requestSubscription).toHaveBeenCalledWith({ serverPublicKey: 'CLAVE' });
    expect(servicio.estado()).toBe('activo');
  });

  it('avisa si el servidor no tiene claves VAPID', async () => {
    const { servicio, http } = crear(true, null);
    await esperar();

    const activando = servicio.activar();
    http.expectOne('/api/v1/push/clave-publica').flush({ habilitado: false, clave: '' });
    await activando;

    expect(servicio.estado()).toBe('no-configurado');
  });

  it('desactivar quita la suscripción del navegador y del servidor', async () => {
    const { servicio, http, swPush } = crear(true, SUSCRIPCION);
    await esperar();

    const desactivando = servicio.desactivar();
    await esperar();
    http
      .expectOne((r) => r.method === 'DELETE' && r.params.get('endpoint') === SUSCRIPCION.endpoint)
      .flush(null, { status: 204, statusText: 'No Content' });
    await desactivando;

    expect(swPush.unsubscribe).toHaveBeenCalled();
    expect(servicio.estado()).toBe('inactivo');
  });

  it('al entrar otro usuario, la suscripción del navegador pasa a ser suya', async () => {
    const sesion = sesionFalsa(null);
    const { http } = crear(true, SUSCRIPCION, sesion);
    TestBed.tick();
    await esperar();
    http.expectNone('/api/v1/push/suscripciones');

    sesion.usuario.set(usuarioSesion({ id: 2 }));
    TestBed.tick();
    await esperar();

    const registro = http.expectOne({ method: 'POST', url: '/api/v1/push/suscripciones' });
    expect(registro.request.body).toEqual(SUSCRIPCION.toJSON());
  });
});
