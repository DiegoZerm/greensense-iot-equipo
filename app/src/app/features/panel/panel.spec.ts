import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { EstadoActualService } from '../../core/estado-actual.service';
import { alerta, lectura, nodo } from '../../core/fabricas-pruebas';
import { EstadoActual } from '../../core/modelos';
import { Panel } from './panel';

describe('Panel', () => {
  const estados = signal<EstadoActual[]>([]);
  const servicio = {
    estados,
    enVivo: signal(true),
    error: signal<string | null>(null),
    conectar: vi.fn(),
    desconectar: vi.fn(),
  };

  async function mostrar(valor: EstadoActual[]): Promise<HTMLElement> {
    estados.set(valor);
    await TestBed.configureTestingModule({
      imports: [Panel],
      providers: [{ provide: EstadoActualService, useValue: servicio }],
    }).compileComponents();
    const fixture = TestBed.createComponent(Panel);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  const texto = (raiz: HTMLElement, selector: string) =>
    raiz.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();

  const estado = (cambios: Partial<EstadoActual> = {}): EstadoActual => ({
    nodo: nodo(),
    ultima: lectura(),
    alertas: [],
    ...cambios,
  });

  it('muestra los valores de la última lectura', async () => {
    const raiz = await mostrar([estado()]);

    expect(texto(raiz, '[data-variable="temperatura"] dd')).toBe('24.3 °C');
    expect(texto(raiz, '[data-variable="humedad_aire"] dd')).toBe('68 %');
    expect(texto(raiz, '.estado')).toBe('conectado');
  });

  it('distingue un nodo sin sensor de suelo de un valor faltante', async () => {
    const raiz = await mostrar([
      estado({
        nodo: nodo({ sensor_suelo: false }),
        ultima: lectura({ humedad_sustrato: null, temperatura: null }),
      }),
    ]);

    expect(texto(raiz, '[data-variable="humedad_sustrato"] dd')).toBe('Sin sensor');
    expect(texto(raiz, '[data-variable="temperatura"] dd')).toBe('—');
  });

  it('muestra un valor de cero', async () => {
    const raiz = await mostrar([estado({ ultima: lectura({ temperatura: 0 }) })]);

    expect(texto(raiz, '[data-variable="temperatura"] dd')).toBe('0 °C');
  });

  it('colorea cada variable según su alerta más grave', async () => {
    const raiz = await mostrar([
      estado({
        alertas: [
          alerta({ id: 1, variable: 'temperatura', severidad: 'advertencia' }),
          alerta({ id: 2, variable: 'temperatura', tipo: 'sensor', severidad: 'critica' }),
          alerta({ id: 3, variable: 'humedad_aire', severidad: 'advertencia' }),
        ],
      }),
    ]);

    const clase = (v: string) => raiz.querySelector(`[data-variable="${v}"]`)?.className;
    expect(clase('temperatura')).toContain('critica');
    expect(clase('humedad_aire')).toContain('advertencia');
    expect(clase('humedad_sustrato')).toContain('normal');
  });

  it('muestra las alertas del nodo completo', async () => {
    const raiz = await mostrar([
      estado({
        alertas: [
          alerta({
            tipo: 'desconexion',
            variable: null,
            severidad: 'critica',
            mensaje: 'El nodo no envía lecturas desde hace 7 min',
          }),
        ],
      }),
    ]);

    expect(texto(raiz, '.alerta-nodo.critica')).toBe('El nodo no envía lecturas desde hace 7 min');
  });

  it('avisa cuando no hay nodos', async () => {
    const raiz = await mostrar([]);

    expect(texto(raiz, '.vacio')).toBe('No hay nodos registrados.');
  });

  it('se conecta al crearse', async () => {
    await mostrar([]);

    expect(servicio.conectar).toHaveBeenCalled();
  });
});
