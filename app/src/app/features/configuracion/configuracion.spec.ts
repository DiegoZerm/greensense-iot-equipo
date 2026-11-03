import { Type } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { ConfiguracionService } from '../../core/configuracion.service';
import { nodo, proveerSesion, sesionFalsa, usuarioSesion } from '../../core/fabricas-pruebas';
import { Cultivo } from '../../core/modelos';
import { Configuracion } from './configuracion';
import { Cultivos } from './cultivos';
import { Nodos } from './nodos';
import { Usuarios } from './usuarios';

const HOJA: Cultivo = {
  id: 'hortalizas-hoja',
  nombre: 'Hortalizas de hoja',
  umbrales: [
    {
      variable: 'temperatura',
      minimo: 18,
      maximo: 28,
      margen: 2,
      tiempo_bajo_s: 300,
      tiempo_alto_s: 300,
    },
    {
      variable: 'humedad_aire',
      minimo: 60,
      maximo: 80,
      margen: 5,
      tiempo_bajo_s: 300,
      tiempo_alto_s: 300,
    },
  ],
  hongos: { humedad_minima: 85, temperatura_minima: 20, tiempo_minimo_s: 3600 },
};

function servicioFalso() {
  return {
    cultivos: vi.fn(() => of([HOJA])),
    guardarCultivo: vi.fn((c: Cultivo) => of(c)),
    crearCultivo: vi.fn((c: Cultivo) => of(c)),
    borrarCultivo: vi.fn(() => of(undefined)),
    nodos: vi.fn(() => of([nodo({ nombre: 'Puerta' })])),
    invernaderos: vi.fn(() => of([{ id: 'inv1', nombre: 'Uno', cultivo_id: 'hortalizas-hoja' }])),
    modificarNodo: vi.fn((_: string, cambios: object) => of(nodo({ ...cambios }))),
    usuarios: vi.fn(() =>
      of([usuarioSesion(), usuarioSesion({ id: 2, nombre: 'Beto', rol: 'operador' })]),
    ),
    modificarUsuario: vi.fn((id: number, cambios: object) => of(usuarioSesion({ id, ...cambios }))),
  };
}

async function mostrar<T>(componente: Type<T>, sesion = sesionFalsa()) {
  const servicio = servicioFalso();
  await TestBed.configureTestingModule({
    imports: [componente],
    providers: [
      provideRouter([]),
      proveerSesion(sesion),
      { provide: ConfiguracionService, useValue: servicio },
    ],
  }).compileComponents();
  const fixture = TestBed.createComponent(componente);
  await fixture.whenStable();
  return { raiz: fixture.nativeElement as HTMLElement, fixture, servicio };
}

describe('Configuración', () => {
  it('muestra solo las pestañas que permite el rol', async () => {
    const tecnico = sesionFalsa(usuarioSesion({ rol: 'tecnico' }, ['gestionar_nodos']));
    const { raiz } = await mostrar(Configuracion, tecnico);

    expect([...raiz.querySelectorAll('.pestanas a')].map((a) => a.textContent?.trim())).toEqual([
      'Nodos',
    ]);
  });

  it('el administrador ve todas', async () => {
    const { raiz } = await mostrar(Configuracion);
    expect(raiz.querySelectorAll('.pestanas a')).toHaveLength(4);
  });
});

describe('Cultivos', () => {
  it('carga el predeterminado y guarda los tiempos en segundos', async () => {
    const { raiz, fixture, servicio } = await mostrar(Cultivos);
    const filas = raiz.querySelectorAll('tbody tr');
    expect(filas).toHaveLength(3);
    // El sustrato no tiene umbral en este cultivo: aparece desmarcado.
    expect((filas[2].querySelector('input[type="checkbox"]') as HTMLInputElement).checked).toBe(
      false,
    );

    const maximo = filas[0].querySelectorAll('input[type="number"]')[1] as HTMLInputElement;
    maximo.value = '30';
    maximo.dispatchEvent(new Event('input'));
    const criticaAlta = filas[0].querySelectorAll('input[type="number"]')[4] as HTMLInputElement;
    criticaAlta.value = '10';
    criticaAlta.dispatchEvent(new Event('input'));
    await fixture.whenStable();
    raiz.querySelector('form')!.dispatchEvent(new Event('submit'));

    const guardado = servicio.guardarCultivo.mock.calls[0][0] as Cultivo;
    expect(guardado.id).toBe('hortalizas-hoja');
    expect(guardado.umbrales.map((u) => u.variable)).toEqual(['temperatura', 'humedad_aire']);
    expect(guardado.umbrales[0]).toMatchObject({ maximo: 30, tiempo_alto_s: 600 });
    expect(guardado.hongos.tiempo_minimo_s).toBe(3600);
  });

  it('el predeterminado no se puede borrar', async () => {
    const { raiz } = await mostrar(Cultivos);
    expect(raiz.querySelector('.peligro')).toBeNull();
  });
});

describe('Nodos', () => {
  it('da de baja un nodo tras confirmar', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { raiz, fixture, servicio } = await mostrar(Nodos);

    (raiz.querySelector('[data-nodo="nodo1"] .peligro') as HTMLButtonElement).click();
    await fixture.whenStable();

    expect(servicio.modificarNodo).toHaveBeenCalledWith('nodo1', { activo: false });
    expect(raiz.querySelector('[data-nodo="nodo1"]')?.className).toContain('inactivo');
    expect(raiz.textContent).toContain('De baja');
  });
});

describe('Usuarios', () => {
  it('cambia el rol y desactiva', async () => {
    const { raiz, fixture, servicio } = await mostrar(Usuarios);
    const fila = raiz.querySelector('[data-usuario="2"]')!;

    const rol = fila.querySelector('select') as HTMLSelectElement;
    rol.value = 'supervisor';
    rol.dispatchEvent(new Event('change'));
    (fila.querySelector('.peligro') as HTMLButtonElement).click();
    await fixture.whenStable();

    expect(servicio.modificarUsuario).toHaveBeenCalledWith(2, { rol: 'supervisor' });
    expect(servicio.modificarUsuario).toHaveBeenCalledWith(2, { activo: false });
  });

  it('marca al usuario de la sesión', async () => {
    const { raiz } = await mostrar(Usuarios);
    expect(raiz.querySelector('[data-usuario="1"]')?.textContent).toContain('(tú)');
  });
});
