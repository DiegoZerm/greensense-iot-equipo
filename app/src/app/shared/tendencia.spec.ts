import { TestBed } from '@angular/core/testing';
import { PuntoTendencia, Tendencia } from './tendencia';

const DESDE = Date.parse('2026-11-02T06:00:00Z');
const MIN = 60_000;
const p = (minuto: number, valor: number): PuntoTendencia => ({ t: DESDE + minuto * MIN, valor });

async function mostrar(puntos: PuntoTendencia[]) {
  await TestBed.configureTestingModule({ imports: [Tendencia] }).compileComponents();
  const fixture = TestBed.createComponent(Tendencia);
  const entradas = {
    nombre: 'Temperatura',
    unidad: '°C',
    puntos,
    desde: DESDE,
    hasta: DESDE + 360 * MIN,
    periodoMs: MIN,
    horas: 6,
  };
  for (const [clave, valor] of Object.entries(entradas)) {
    fixture.componentRef.setInput(clave, valor);
  }
  await fixture.whenStable();
  return { raiz: fixture.nativeElement as HTMLElement, fixture };
}

describe('Tendencia', () => {
  it('sin lecturas no dibuja nada', async () => {
    const { raiz } = await mostrar([]);
    expect(raiz.querySelector('svg')).toBeNull();
    expect(raiz.querySelector('.pie')).toBeNull();
  });

  it('corta la línea donde faltan lecturas', async () => {
    const { raiz } = await mostrar([p(0, 20), p(1, 21), p(30, 22), p(31, 23)]);
    expect(raiz.querySelector('.linea')!.getAttribute('d')!.match(/M/g)).toHaveLength(2);
  });

  it('dice la ventana, el mínimo y el máximo, también para lectores de pantalla', async () => {
    const { raiz } = await mostrar([p(0, 20.5), p(1, 24)]);
    expect(raiz.querySelector('.pie')!.textContent).toBe('últimas 6 h · mín 20.5 °C · máx 24 °C');
    expect(raiz.querySelector('.lienzo')!.getAttribute('aria-label')).toContain('Temperatura');
  });

  it('una variable plana no llena toda la altura', async () => {
    const { raiz } = await mostrar([p(0, 20), p(1, 20.1)]);
    const alturas = [
      ...raiz
        .querySelector('.linea')!
        .getAttribute('d')!
        .matchAll(/,([\d.]+)/g),
    ];
    const diferencia = Math.abs(Number(alturas[0][1]) - Number(alturas[1][1]));
    expect(diferencia).toBeLessThan(15);
  });

  it('al pasar el puntero muestra el valor y la hora del punto más cercano', async () => {
    const { raiz, fixture } = await mostrar([p(0, 20), p(180, 25)]);
    const lienzo = raiz.querySelector('.lienzo') as HTMLElement;
    lienzo.getBoundingClientRect = () => ({ left: 0, width: 360 }) as DOMRect;

    expect(raiz.querySelector('.guia')).toBeNull();
    lienzo.dispatchEvent(new MouseEvent('pointermove', { clientX: 170 }));
    await fixture.whenStable();
    expect(raiz.querySelector('.guia')).not.toBeNull();
    expect(raiz.querySelector('.pie')!.textContent).toBe('03:00 · 25 °C');

    lienzo.dispatchEvent(new MouseEvent('pointerleave'));
    await fixture.whenStable();
    expect(raiz.querySelector('.pie')!.textContent).toContain('últimas 6 h');
  });
});
