import { TestBed } from '@angular/core/testing';
import { GraficaSerie, Punto, masCercano } from './grafica-serie';

const DESDE = Date.parse('2026-11-02T06:00:00Z');
const MIN = 60_000;

const punto = (minuto: number, valor: number | null, extra: Partial<Punto> = {}): Punto => ({
  t: DESDE + minuto * MIN,
  valor,
  ...extra,
});

async function mostrar(puntos: Punto[], rango: { minimo: number; maximo: number } | null = null) {
  await TestBed.configureTestingModule({ imports: [GraficaSerie] }).compileComponents();
  const fixture = TestBed.createComponent(GraficaSerie);
  fixture.componentRef.setInput('titulo', 'Temperatura');
  fixture.componentRef.setInput('unidad', '°C');
  fixture.componentRef.setInput('puntos', puntos);
  fixture.componentRef.setInput('desde', DESDE);
  fixture.componentRef.setInput('hasta', DESDE + 24 * 60 * MIN);
  fixture.componentRef.setInput('pasoMs', MIN);
  fixture.componentRef.setInput('rango', rango);
  await fixture.whenStable();
  return { raiz: fixture.nativeElement as HTMLElement, fixture };
}

describe('GraficaSerie', () => {
  it('en un lienzo angosto salta etiquetas de la hora para que no se encimen', async () => {
    const { raiz, fixture } = await mostrar([punto(0, 20), punto(1, 21)]);
    const etiquetas = () => raiz.querySelectorAll('text.eje[text-anchor="middle"]').length;
    expect(etiquetas()).toBe(8); // cada 3 h

    // Lo que mediría el ResizeObserver en un teléfono.
    (fixture.componentInstance as unknown as { ancho: { set(v: number): void } }).ancho.set(330);
    await fixture.whenStable();

    expect(etiquetas()).toBe(4); // cada 6 h
    expect(raiz.querySelector('svg')!.getAttribute('viewBox')).toBe('0 0 330 200');
  });

  it('corta la línea donde faltan lecturas', async () => {
    const { raiz } = await mostrar([
      punto(0, 20),
      punto(1, 21),
      punto(2, 22),
      // hueco de 30 min: el nodo no mandó nada
      punto(32, 23),
      punto(33, 24),
      punto(34, null),
      punto(35, 25),
    ]);

    const d = raiz.querySelector('.linea')!.getAttribute('d')!;
    expect(d.match(/M/g)).toHaveLength(2);
    // El punto aislado después del nulo se dibuja como marcador.
    expect(raiz.querySelectorAll('circle.marcador')).toHaveLength(1);
  });

  it('dibuja el rango adecuado y lo nombra', async () => {
    const { raiz } = await mostrar([punto(0, 20), punto(1, 30)], { minimo: 18, maximo: 28 });

    expect(raiz.querySelector('rect.franja')).not.toBeNull();
    expect(raiz.querySelector('figcaption')!.textContent).toContain('Rango adecuado 18 a 28 °C');
  });

  it('sin datos lo dice y no ofrece tabla', async () => {
    const { raiz } = await mostrar([punto(0, null)]);

    expect(raiz.querySelector('.vacio')!.textContent).toContain('Sin lecturas');
    expect(raiz.querySelector('.ver-tabla')).toBeNull();
  });

  it('con agregados dibuja la banda de mínimo a máximo y la tabla trae los tres valores', async () => {
    const { raiz, fixture } = await mostrar([
      punto(0, 20, { minimo: 18, maximo: 22 }),
      punto(1, 24, { minimo: 21, maximo: 27.5 }),
    ]);
    expect(raiz.querySelector('.banda')!.getAttribute('d')).toMatch(/^M.*Z$/);

    (raiz.querySelector('.ver-tabla') as HTMLButtonElement).click();
    await fixture.whenStable();

    const celdas = [...raiz.querySelectorAll('tbody tr:last-child td')].map((c) =>
      c.textContent?.trim(),
    );
    expect(celdas.slice(1)).toEqual(['24 °C', '21 °C', '27.5 °C']);
  });

  it('al pasar el puntero muestra el valor más cercano', async () => {
    const { raiz, fixture } = await mostrar([punto(0, 20), punto(720, 23.46), punto(1439, 19)]);
    const svg = raiz.querySelector('svg')!;
    svg.getBoundingClientRect = () => ({ left: 0, width: 720 }) as DOMRect;

    // x = 44 + 676/2: la mitad del día.
    svg.dispatchEvent(new PointerEvent('pointermove', { clientX: 382 }));
    await fixture.whenStable();

    const globo = raiz.querySelector('.globo')!;
    expect(globo.querySelector('strong')!.textContent).toBe('23.5 °C');
    expect(globo.textContent).toContain('12:00');

    svg.dispatchEvent(new PointerEvent('pointerleave'));
    await fixture.whenStable();
    expect(raiz.querySelector('.globo')).toBeNull();
  });
});

describe('masCercano', () => {
  const puntos = [punto(0, 1), punto(10, null), punto(20, 3), punto(30, 4)];

  it('salta los puntos sin valor', () => {
    expect(masCercano(puntos, DESDE + 11 * MIN)).toBe(2);
    expect(masCercano(puntos, DESDE + 9 * MIN)).toBe(0);
  });

  it('en los extremos toma el primero o el último', () => {
    expect(masCercano(puntos, DESDE - MIN)).toBe(0);
    expect(masCercano(puntos, DESDE + 99 * MIN)).toBe(3);
  });

  it('sin puntos no hay ninguno', () => {
    expect(masCercano([], DESDE)).toBeNull();
  });
});
