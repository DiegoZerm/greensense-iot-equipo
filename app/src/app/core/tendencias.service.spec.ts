import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Subject } from 'rxjs';
import { lectura, nodo } from './fabricas-pruebas';
import { Lectura } from './modelos';
import { TendenciasService } from './tendencias.service';
import { EventoTiempoReal, TiempoRealService } from './tiempo-real.service';

describe('TendenciasService', () => {
  const eventos = new Subject<EventoTiempoReal>();
  const abierta = new Subject<void>();
  let http: HttpTestingController;
  let servicio: TendenciasService;

  const hace = (minutos: number) => new Date(Date.now() - minutos * 60_000).toISOString();
  const coincide = (r: { url: string }) => r.url === '/api/v1/lecturas';
  const llega = (l: Partial<Lectura>) =>
    eventos.next({ tipo: 'lectura', nodo: nodo(), lectura: lectura(l) });

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: TiempoRealService, useValue: { eventos, abierta } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    servicio = TestBed.inject(TendenciasService);
  });

  it('carga una sola vez cada nodo, con las últimas 6 horas', () => {
    servicio.seguir(['nodo1']);
    servicio.seguir(['nodo1']);

    const pedido = http.expectOne(coincide);
    const desde = Date.parse(pedido.request.params.get('desde')!);
    expect(Math.round((Date.now() - desde) / 3_600_000)).toBe(6);
    pedido.flush({ lecturas: [lectura({ ts: hace(10) })], completa: true });

    expect(servicio.lecturas('nodo1')).toHaveLength(1);
  });

  it('agrega en orden las lecturas que llegan, sin repetirlas ni pasar de la ventana', () => {
    servicio.seguir(['nodo1']);
    const reciente = hace(1);
    http.expectOne(coincide).flush({ lecturas: [lectura({ ts: reciente })], completa: true });

    const anterior = hace(5);
    llega({ ts: reciente });
    llega({ ts: anterior });
    llega({ ts: hace(7 * 60) });

    expect(servicio.lecturas('nodo1').map((l) => l.ts)).toEqual([anterior, reciente]);
  });

  it('ignora a los nodos que no sigue y recarga al reconectar', () => {
    llega({ ts: hace(1) });
    expect(servicio.lecturas('nodo1')).toEqual([]);

    servicio.seguir(['nodo1']);
    http.expectOne(coincide).flush({ lecturas: [], completa: true });
    abierta.next();
    http.expectOne(coincide).flush({ lecturas: [lectura({ ts: hace(2) })], completa: true });

    expect(servicio.lecturas('nodo1')).toHaveLength(1);
  });

  it('si la consulta falla se queda sin gráfica, sin error', () => {
    servicio.seguir(['nodo1']);
    http.expectOne(coincide).flush('no', { status: 403, statusText: 'Forbidden' });

    expect(servicio.lecturas('nodo1')).toEqual([]);
  });
});
