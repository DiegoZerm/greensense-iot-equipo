import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { App } from './app';
import { AlertasService } from './core/alertas.service';
import { SesionFalsa, proveerSesion, sesionFalsa, usuarioSesion } from './core/fabricas-pruebas';
import { PushService } from './core/push.service';

describe('App', () => {
  const alertas = { criticasActivas: signal(0), conectar: vi.fn(), desconectar: vi.fn() };
  const push = {
    estado: signal('inactivo'),
    error: signal(null),
    desactivar: vi.fn(async () => undefined),
  };

  async function mostrar(sesion: SesionFalsa = sesionFalsa(), criticas = 0) {
    alertas.criticasActivas.set(criticas);
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter([]),
        proveerSesion(sesion),
        { provide: AlertasService, useValue: alertas },
        { provide: PushService, useValue: push },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    return { raiz: fixture.nativeElement as HTMLElement, fixture };
  }

  const enlaces = (raiz: HTMLElement) =>
    [...raiz.querySelectorAll('nav a')].map((a) => a.textContent?.trim());

  beforeEach(() => vi.clearAllMocks());

  it('al administrador le muestra toda la navegación', async () => {
    const { raiz } = await mostrar();

    expect(raiz.querySelector('h1')?.textContent).toContain('GreenSense IoT');
    expect(enlaces(raiz)).toEqual(['Panel', 'Alertas', 'Historial', 'Configuración', 'Bitácora']);
    expect(raiz.querySelector('.usuario')?.textContent).toContain('Ana');
    expect(raiz.querySelector('.usuario')?.textContent).toContain('Administrador');
  });

  it('al operador le muestra el panel, las alertas y el historial', async () => {
    const operador = usuarioSesion({ rol: 'operador' }, [
      'ver_panel',
      'notificaciones_cultivo',
      'consultar_historial',
      'atender_alertas',
    ]);
    const { raiz } = await mostrar(sesionFalsa(operador));

    expect(enlaces(raiz)).toEqual(['Panel', 'Alertas', 'Historial']);
  });

  it('al técnico le muestra configuración pero no la bitácora', async () => {
    const tecnico = usuarioSesion({ rol: 'tecnico' }, ['ver_panel', 'gestionar_nodos']);
    const { raiz } = await mostrar(sesionFalsa(tecnico));

    expect(enlaces(raiz)).toEqual(['Panel', 'Alertas', 'Configuración']);
  });

  it('sin sesión no hay barra ni conexión en tiempo real', async () => {
    const { raiz } = await mostrar(sesionFalsa(null));

    expect(raiz.querySelector('header')).toBeNull();
    expect(alertas.conectar).not.toHaveBeenCalled();
  });

  it('con sesión cuenta las alertas críticas activas', async () => {
    const { raiz } = await mostrar(sesionFalsa(), 2);

    expect(alertas.conectar).toHaveBeenCalledOnce();
    expect(raiz.querySelector('.contador')?.textContent).toBe('2');
  });

  it('ofrece activar las notificaciones', async () => {
    const { raiz } = await mostrar();

    expect(raiz.querySelector('gs-boton-notificaciones button')?.textContent).toContain(
      'Activar notificaciones',
    );
  });

  it('al salir apaga las notificaciones del navegador, cierra la sesión y va al login', async () => {
    push.estado.set('activo');
    const sesion = sesionFalsa();
    const { raiz, fixture } = await mostrar(sesion);
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

    (raiz.querySelector('.usuario button') as HTMLButtonElement).click();
    await fixture.whenStable();

    expect(push.desactivar).toHaveBeenCalled();
    expect(sesion.cerrar).toHaveBeenCalled();
    expect(navegar).toHaveBeenCalledWith(['/login']);
    expect(raiz.querySelector('header')).toBeNull();
    expect(alertas.desconectar).toHaveBeenCalled();
  });
});
