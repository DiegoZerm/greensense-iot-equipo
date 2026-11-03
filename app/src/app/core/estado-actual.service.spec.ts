import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { EstadoActualService } from './estado-actual.service';
import { FuenteFalsa, proveerSesion, alerta, lectura, nodo } from './fabricas-pruebas';
import { EstadoActual } from './modelos';
import { FABRICA_EVENTOS } from './tiempo-real.service';

describe('EstadoActualService', () => {
  let servicio: EstadoActualService;
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
    servicio = TestBed.inject(EstadoActualService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function responder(estados: EstadoActual[]): void {
    http.expectOne('/api/v1/lecturas/ultimas').flush(estados);
  }

  const estado = (cambios: Partial<EstadoActual> = {}): EstadoActual => ({
    nodo: nodo(),
    ultima: lectura(),
    alertas: [],
    ...cambios,
  });

  it('carga el estado inicial', () => {
    servicio.conectar();
    responder([estado()]);

    expect(servicio.estados()).toEqual([estado()]);
  });

  it('ordena los nodos por invernadero y por id', () => {
    servicio.conectar();
    responder([
      estado({ nodo: nodo({ id: 'b', invernadero_id: 'inv2' }) }),
      estado({ nodo: nodo({ id: 'z', invernadero_id: 'inv1' }) }),
      estado({ nodo: nodo({ id: 'a', invernadero_id: 'inv1' }) }),
    ]);

    expect(servicio.estados().map((e) => e.nodo.id)).toEqual(['a', 'z', 'b']);
  });

  it('aplica una lectura nueva que llega en tiempo real', () => {
    servicio.conectar();
    responder([estado()]);

    const nueva = lectura({ seq: 1, ts: '2026-11-01T16:01:00Z', temperatura: 25 });
    fuente.emitir('lectura', { nodo: nodo(), lectura: nueva });

    expect(servicio.estados()[0].ultima).toEqual(nueva);
  });

  it('no reemplaza la lectura por una reenviada más vieja', () => {
    servicio.conectar();
    responder([estado()]);

    fuente.emitir('lectura', { nodo: nodo(), lectura: lectura({ ts: '2026-11-01T15:00:00Z' }) });

    expect(servicio.estados()[0].ultima).toEqual(lectura());
  });

  it('un cambio de estado conserva la lectura y las alertas', () => {
    servicio.conectar();
    responder([estado({ alertas: [alerta()] })]);

    fuente.emitir('nodo', { nodo: nodo({ estado: 'desconectado' }) });

    expect(servicio.estados()[0]).toEqual(
      estado({ nodo: nodo({ estado: 'desconectado' }), alertas: [alerta()] }),
    );
  });

  it('agrega, actualiza y quita alertas activas', () => {
    servicio.conectar();
    responder([estado()]);

    fuente.emitir('alerta', { alerta: alerta() });
    expect(servicio.estados()[0].alertas).toEqual([alerta()]);

    fuente.emitir('alerta', { alerta: alerta({ severidad: 'critica' }) });
    expect(servicio.estados()[0].alertas).toEqual([alerta({ severidad: 'critica' })]);

    fuente.emitir('alerta', { alerta: alerta({ activa: false }) });
    expect(servicio.estados()[0].alertas).toEqual([]);
  });

  it('recarga al reconectar', () => {
    servicio.conectar();
    responder([]);

    fuente.emitir('open');
    responder([estado()]);

    expect(servicio.estados()).toHaveLength(1);
    expect(servicio.enVivo()).toBe(true);
  });

  it('muestra un error si el servidor no responde', () => {
    servicio.conectar();
    http
      .expectOne('/api/v1/lecturas/ultimas')
      .flush(null, { status: 502, statusText: 'Bad Gateway' });

    expect(servicio.error()).toContain('No se pudo');
  });
});
