import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AlertasService } from './alertas.service';
import { FuenteFalsa, proveerSesion, alerta } from './fabricas-pruebas';
import { FABRICA_EVENTOS } from './tiempo-real.service';

describe('AlertasService', () => {
  let servicio: AlertasService;
  let http: HttpTestingController;
  let fuente: FuenteFalsa;

  beforeEach(() => {
    fuente = new FuenteFalsa();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: FABRICA_EVENTOS, useValue: () => fuente as unknown as EventSource },
        proveerSesion(),
      ],
    });
    servicio = TestBed.inject(AlertasService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  const responder = (alertas: unknown[]) =>
    http.expectOne((r) => r.url === '/api/v1/alertas').flush(alertas);

  it('pone primero las activas y luego las más recientes', () => {
    servicio.conectar();
    responder([
      alerta({ id: 1, activa: false, iniciada_en: '2026-11-01T18:00:00Z' }),
      alerta({ id: 2, iniciada_en: '2026-11-01T16:00:00Z' }),
      alerta({ id: 3, iniciada_en: '2026-11-01T17:00:00Z' }),
    ]);

    expect(servicio.alertas().map((a) => a.id)).toEqual([3, 2, 1]);
  });

  it('cuenta las críticas activas', () => {
    servicio.conectar();
    responder([
      alerta({ id: 1, severidad: 'critica' }),
      alerta({ id: 2, severidad: 'critica', activa: false }),
      alerta({ id: 3 }),
    ]);

    expect(servicio.criticasActivas()).toBe(1);
  });

  it('agrega y actualiza alertas en tiempo real', () => {
    servicio.conectar();
    responder([]);

    fuente.emitir('alerta', { alerta: alerta() });
    fuente.emitir('alerta', { alerta: alerta({ severidad: 'critica' }) });

    expect(servicio.alertas()).toEqual([alerta({ severidad: 'critica' })]);
  });

  it('atender actualiza la alerta', () => {
    servicio.conectar();
    responder([alerta()]);

    servicio.atender(1).subscribe();
    const atendida = alerta({ atendida_en: '2026-11-01T16:05:00Z' });
    http.expectOne({ method: 'POST', url: '/api/v1/alertas/1/atender' }).flush(atendida);

    expect(servicio.alertas()).toEqual([atendida]);
  });
});
