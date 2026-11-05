import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AlertasService } from '../../core/alertas.service';
import { EstadoActualService } from '../../core/estado-actual.service';
import {
  alerta,
  lectura,
  nodo,
  proveerSesion,
  sesionFalsa,
  usuarioSesion,
} from '../../core/fabricas-pruebas';
import { Alerta } from '../../core/modelos';
import { Alertas } from './alertas';

describe('Alertas', () => {
  const lista = signal<Alerta[]>([]);
  const servicio = {
    alertas: lista,
    error: signal<string | null>(null),
    conectar: vi.fn(),
    desconectar: vi.fn(),
    atender: vi.fn(() => of(alerta())),
  };
  const estadoActual = {
    estados: signal([
      { nodo: nodo({ nombre: 'Nodo de la puerta' }), ultima: lectura(), alertas: [] },
    ]),
    conectar: vi.fn(),
    desconectar: vi.fn(),
  };

  async function mostrar(alertas: Alerta[], sesion = sesionFalsa()) {
    lista.set(alertas);
    await TestBed.configureTestingModule({
      imports: [Alertas],
      providers: [
        { provide: AlertasService, useValue: servicio },
        { provide: EstadoActualService, useValue: estadoActual },
        proveerSesion(sesion),
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(Alertas);
    await fixture.whenStable();
    return { raiz: fixture.nativeElement as HTMLElement, fixture };
  }

  it('muestra solo las activas y luego todas', async () => {
    const { raiz, fixture } = await mostrar([
      alerta({ id: 1 }),
      alerta({ id: 2, activa: false, resuelta_en: '2026-11-01T17:00:00Z' }),
    ]);
    expect(raiz.querySelectorAll('[data-alerta]')).toHaveLength(1);

    (raiz.querySelectorAll('.filtro button')[1] as HTMLButtonElement).click();
    await fixture.whenStable();

    expect(raiz.querySelectorAll('[data-alerta]')).toHaveLength(2);
  });

  it('muestra severidad, nodo, mensaje y recomendación', async () => {
    const { raiz } = await mostrar([alerta({ severidad: 'critica' })]);

    const tarjeta = raiz.querySelector('[data-alerta="1"]')!;
    expect(tarjeta.className).toContain('critica');
    expect(tarjeta.querySelector('.tipo')?.textContent).toContain('Nodo de la puerta');
    expect(tarjeta.querySelector('.recomendacion')?.textContent).toContain('Ventilar');
  });

  it('en una desconexión muestra la hora de la última lectura', async () => {
    const { raiz } = await mostrar([
      alerta({ tipo: 'desconexion', variable: null, fuera_desde: '2026-11-01T15:12:00Z' }),
    ]);

    expect(raiz.querySelector('footer')?.textContent).toContain('Última lectura');
  });

  it('permite marcarla como atendida', async () => {
    const { raiz } = await mostrar([alerta({ id: 7 })]);

    (raiz.querySelector('footer button') as HTMLButtonElement).click();

    expect(servicio.atender).toHaveBeenCalledWith(7);
  });

  it('una alerta atendida ya no tiene el botón', async () => {
    const { raiz } = await mostrar([alerta({ atendida_en: '2026-11-01T16:05:00Z' })]);

    expect(raiz.querySelector('footer button')).toBeNull();
    expect(raiz.querySelector('.atendida')).not.toBeNull();
  });

  it('dice quién atendió la alerta', async () => {
    const { raiz } = await mostrar([
      alerta({ atendida_en: '2026-11-01T16:05:00Z', atendida_por: 2, atendida_por_nombre: 'Beto' }),
    ]);

    expect(raiz.querySelector('.atendida')?.textContent).toContain('por Beto');
  });

  it('sin el permiso de atender no hay botón', async () => {
    const soloVer = sesionFalsa(usuarioSesion({ rol: 'operador' }, ['ver_panel']));
    const { raiz } = await mostrar([alerta()], soloVer);

    expect(raiz.querySelector('footer button')).toBeNull();
  });
});
