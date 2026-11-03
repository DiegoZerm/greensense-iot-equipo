import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';
import { ConfiguracionService } from '../../core/configuracion.service';
import {
  lectura,
  nodo,
  proveerSesion,
  sesionFalsa,
  usuarioSesion,
} from '../../core/fabricas-pruebas';
import { HistorialService } from '../../core/historial.service';
import { Resumen } from '../../core/modelos';
import { hoyLocal } from '../../core/tiempo';
import { Historial } from './historial';

const RESUMEN: Resumen = {
  nodo_id: 'nodo1',
  desde: '',
  hasta: '',
  lecturas: 1380,
  esperadas: 1440,
  perdidas: 60,
  porcentaje_perdidas: 4.17,
  variables: {
    temperatura: { minimo: 15.2, maximo: 29.8, promedio: 22.4, n: 1380 },
    humedad_aire: { minimo: 50, maximo: 80, promedio: 66, n: 1380 },
    humedad_sustrato: null,
  },
};

describe('Historial', () => {
  let parametros: BehaviorSubject<ReturnType<typeof convertToParamMap>>;
  let historial: {
    lecturas: ReturnType<typeof vi.fn>;
    agregadas: ReturnType<typeof vi.fn>;
    resumen: ReturnType<typeof vi.fn>;
    descargar: ReturnType<typeof vi.fn>;
  };

  async function mostrar(query: Record<string, string> = {}, sesion = sesionFalsa()) {
    parametros = new BehaviorSubject(convertToParamMap(query));
    historial = {
      lecturas: vi.fn(() => of({ lecturas: [lectura()], completa: true })),
      agregadas: vi.fn(() => of([])),
      resumen: vi.fn(() => of(RESUMEN)),
      descargar: vi.fn(() => of({ nombre: 'x.csv', contenido: new Blob() })),
    };
    await TestBed.configureTestingModule({
      imports: [Historial],
      providers: [
        provideRouter([]),
        proveerSesion(sesion),
        { provide: HistorialService, useValue: historial },
        {
          provide: ConfiguracionService,
          useValue: {
            nodos: () => of([nodo({ sensor_suelo: false }), nodo({ id: 'nodo2', nombre: 'Otro' })]),
            invernaderos: () => of([{ id: 'inv1', nombre: 'Uno', cultivo_id: 'hoja' }]),
            cultivos: () =>
              of([
                {
                  id: 'hoja',
                  nombre: 'Hoja',
                  umbrales: [
                    {
                      variable: 'temperatura',
                      minimo: 18,
                      maximo: 28,
                      margen: 2,
                      tiempo_bajo_s: 300,
                      tiempo_alto_s: 300,
                    },
                  ],
                  hongos: { humedad_minima: 85, temperatura_minima: 20, tiempo_minimo_s: 3600 },
                },
              ]),
          },
        },
        {
          provide: ActivatedRoute,
          useValue: { queryParamMap: parametros, snapshot: { queryParamMap: parametros.value } },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(Historial);
    await fixture.whenStable();
    return { raiz: fixture.nativeElement as HTMLElement, fixture };
  }

  it('por defecto muestra hoy del primer nodo activo con lecturas sin agregar', async () => {
    const { raiz } = await mostrar();
    const hoy = hoyLocal();

    expect(historial.lecturas).toHaveBeenCalledWith({
      nodo: 'nodo1',
      desde: `${hoy}T00:00:00-06:00`,
      hasta: expect.stringMatching(/T00:00:00-06:00$/),
    });
    expect(historial.agregadas).not.toHaveBeenCalled();
    // Sin sensor de suelo y sin datos de suelo: dos gráficas.
    expect(raiz.querySelectorAll('gs-grafica-serie')).toHaveLength(2);
    expect(raiz.querySelector('figcaption')!.textContent).toContain('Rango adecuado 18 a 28');
  });

  it('la semana pide agregados por hora de los 7 días que terminan en la fecha', async () => {
    await mostrar({ nodo: 'nodo2', vista: 'semana', fecha: '2026-10-15' });

    expect(historial.agregadas).toHaveBeenCalledWith(
      { nodo: 'nodo2', desde: '2026-10-09T00:00:00-06:00', hasta: '2026-10-16T00:00:00-06:00' },
      'hora',
    );
  });

  it('el mes pide agregados por día', async () => {
    await mostrar({ vista: 'mes', fecha: '2026-10-31' });

    expect(historial.agregadas).toHaveBeenCalledWith(
      expect.objectContaining({ desde: '2026-10-02T00:00:00-06:00' }),
      'dia',
    );
  });

  it('muestra el resumen con las lecturas perdidas', async () => {
    const { raiz } = await mostrar();

    const texto = raiz.querySelector('.resumen')!.textContent!.replace(/\s+/g, ' ');
    expect(texto).toContain('22.4 °C');
    expect(texto).toContain('de 1,440 esperadas · 4.17 % perdidas');
  });

  it('la flecha mueve el periodo y no deja pasar de hoy', async () => {
    const { raiz } = await mostrar({ vista: 'semana', fecha: '2026-10-15' });
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const [anterior, siguiente] = raiz.querySelectorAll<HTMLButtonElement>('.flecha');

    anterior.click();
    expect(navegar).toHaveBeenLastCalledWith(
      [],
      expect.objectContaining({
        queryParams: { nodo: 'nodo1', vista: 'semana', fecha: '2026-10-08' },
      }),
    );

    siguiente.click();
    expect(navegar).toHaveBeenLastCalledWith(
      [],
      expect.objectContaining({
        queryParams: expect.objectContaining({ fecha: '2026-10-22' }),
      }),
    );
  });

  it('solo quien puede exportar ve los botones y descarga del rango mostrado', async () => {
    const operador = sesionFalsa(
      usuarioSesion({ rol: 'operador' }, ['ver_panel', 'consultar_historial']),
    );
    const { raiz: sinBotones } = await mostrar({}, operador);
    expect(sinBotones.querySelector('.exportar')).toBeNull();

    TestBed.resetTestingModule();
    const { raiz } = await mostrar({ fecha: '2026-10-15' });
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    (raiz.querySelector('.exportar button') as HTMLButtonElement).click();

    expect(historial.descargar).toHaveBeenCalledWith('lecturas', {
      nodo: 'nodo1',
      desde: '2026-10-15T00:00:00-06:00',
      hasta: '2026-10-16T00:00:00-06:00',
    });
  });
});
