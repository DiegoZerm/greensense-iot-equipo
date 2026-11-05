import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { proveerSesion, sesionFalsa } from '../../core/fabricas-pruebas';
import { Login } from './login';

describe('Login', () => {
  async function mostrar(parametros: Record<string, string> = {}) {
    const sesion = sesionFalsa(null);
    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [
        provideRouter([]),
        proveerSesion(sesion),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap(parametros) } },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(Login);
    await fixture.whenStable();
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const raiz = fixture.nativeElement as HTMLElement;

    async function enviar(correo: string, contrasena: string) {
      const [campoCorreo, campoContrasena] = raiz.querySelectorAll('input');
      campoCorreo.value = correo;
      campoCorreo.dispatchEvent(new Event('input'));
      campoContrasena.value = contrasena;
      campoContrasena.dispatchEvent(new Event('input'));
      await fixture.whenStable();
      raiz.querySelector('form')!.dispatchEvent(new Event('submit'));
      await fixture.whenStable();
    }
    return { raiz, sesion, navegar, enviar, fixture };
  }

  it('entra y regresa a donde iba', async () => {
    const { sesion, navegar, enviar } = await mostrar({ volver: '/alertas' });
    sesion.iniciar.mockResolvedValue(undefined);

    await enviar('ana@ejemplo.com', 'secreta123');

    expect(sesion.iniciar).toHaveBeenCalledWith('ana@ejemplo.com', 'secreta123');
    expect(navegar).toHaveBeenCalledWith('/alertas');
  });

  it('no redirige fuera de la app', async () => {
    const { sesion, navegar, enviar } = await mostrar({ volver: '//sitio-malo.com' });
    sesion.iniciar.mockResolvedValue(undefined);

    await enviar('ana@ejemplo.com', 'secreta123');

    expect(navegar).toHaveBeenCalledWith('/');
  });

  it('muestra el error del servidor', async () => {
    const { raiz, sesion, enviar, fixture } = await mostrar();
    sesion.iniciar.mockRejectedValue(
      new HttpErrorResponse({ status: 401, error: { detail: 'correo o contraseña incorrectos' } }),
    );

    await enviar('ana@ejemplo.com', 'mala-clave');
    await fixture.whenStable();

    expect(raiz.querySelector('[role="alert"]')?.textContent).toContain(
      'Correo o contraseña incorrectos',
    );
  });

  it('avisa cuando la sesión venció', async () => {
    const { raiz } = await mostrar({ motivo: 'vencida' });

    expect(raiz.textContent).toContain('Tu sesión terminó');
  });
});
