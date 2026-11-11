import { TestBed } from '@angular/core/testing';
import {
  FuenteFalsa,
  SesionFalsa,
  alerta,
  nodo,
  proveerSesion,
  sesionFalsa,
} from './fabricas-pruebas';
import {
  ESPERA_REAPERTURA_MS,
  EventoTiempoReal,
  FABRICA_EVENTOS,
  TiempoRealService,
} from './tiempo-real.service';

describe('TiempoRealService', () => {
  let servicio: TiempoRealService;
  let creadas: FuenteFalsa[];
  let sesion: SesionFalsa;

  beforeEach(() => {
    creadas = [];
    sesion = sesionFalsa();
    TestBed.configureTestingModule({
      providers: [
        {
          provide: FABRICA_EVENTOS,
          useValue: (url: string) => {
            const fuente = Object.assign(new FuenteFalsa(), { url });
            creadas.push(fuente);
            return fuente as unknown as EventSource;
          },
        },
        { provide: ESPERA_REAPERTURA_MS, useValue: 0 },
        proveerSesion(sesion),
      ],
    });
    servicio = TestBed.inject(TiempoRealService);
    TestBed.tick();
  });

  it('comparte una sola conexión y la cierra cuando nadie la usa', () => {
    servicio.conectar();
    servicio.conectar();
    expect(creadas).toHaveLength(1);
    expect(creadas[0].url).toBe('/api/v1/eventos?token=token-1');

    servicio.desconectar();
    expect(creadas[0].cerrada).toBe(false);
    servicio.desconectar();
    expect(creadas[0].cerrada).toBe(true);
  });

  it('reparte los eventos con su tipo', () => {
    const recibidos: EventoTiempoReal[] = [];
    servicio.eventos.subscribe((e) => recibidos.push(e));
    servicio.conectar();

    creadas[0].emitir('nodo', { nodo: nodo() });
    creadas[0].emitir('alerta', { alerta: alerta() });

    expect(recibidos).toEqual([
      { tipo: 'nodo', nodo: nodo() },
      { tipo: 'alerta', alerta: alerta() },
    ]);
  });

  it('avisa al abrirse e indica si está en vivo', () => {
    let aperturas = 0;
    servicio.abierta.subscribe(() => aperturas++);
    servicio.conectar();

    creadas[0].emitir('open');
    expect(servicio.enVivo()).toBe(true);
    expect(aperturas).toBe(1);

    creadas[0].emitir('error');
    expect(servicio.enVivo()).toBe(false);
  });

  it('sin sesión no se conecta', () => {
    sesion.cerrar();
    TestBed.tick();

    servicio.conectar();

    expect(creadas).toHaveLength(0);
  });

  it('al cambiar la sesión reabre con el token nuevo y al cerrarla se desconecta', () => {
    servicio.conectar();

    sesion.token.set('token-2');
    TestBed.tick();
    expect(creadas[0].cerrada).toBe(true);
    expect(creadas[1].url).toBe('/api/v1/eventos?token=token-2');

    sesion.cerrar();
    TestBed.tick();
    expect(creadas[1].cerrada).toBe(true);
    expect(creadas).toHaveLength(2);
  });

  it('si el servidor cierra la conexión, comprueba la sesión y reabre', async () => {
    servicio.conectar();

    Object.assign(creadas[0], { readyState: 2 });
    creadas[0].emitir('error');
    await new Promise((r) => setTimeout(r, 5));

    expect(sesion.comprobar).toHaveBeenCalled();
    expect(creadas).toHaveLength(2);
  });

  it('no reabre si la sesión ya no es válida', async () => {
    servicio.conectar();
    sesion.comprobar.mockResolvedValue(false);

    Object.assign(creadas[0], { readyState: 2 });
    creadas[0].emitir('error');
    await new Promise((r) => setTimeout(r, 5));

    expect(creadas).toHaveLength(1);
  });
});
