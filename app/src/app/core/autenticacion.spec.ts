import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  RedirectCommand,
  Router,
  RouterStateSnapshot,
  UrlTree,
  provideRouter,
} from '@angular/router';
import { permisoGuard, sesionGuard } from './autenticacion';
import { SesionFalsa, proveerSesion, sesionFalsa, usuarioSesion } from './fabricas-pruebas';

describe('Guards de sesión y permisos', () => {
  function configurar(sesion: SesionFalsa) {
    TestBed.configureTestingModule({ providers: [provideRouter([]), proveerSesion(sesion)] });
  }

  const correr = (guard: typeof sesionGuard, url = '/alertas') =>
    TestBed.runInInjectionContext(() =>
      guard({} as ActivatedRouteSnapshot, { url } as RouterStateSnapshot),
    ) as Promise<boolean | UrlTree | RedirectCommand>;

  const texto = (resultado: boolean | UrlTree | RedirectCommand) => {
    const arbol = resultado instanceof RedirectCommand ? resultado.redirectTo : resultado;
    return arbol instanceof UrlTree ? TestBed.inject(Router).serializeUrl(arbol) : arbol;
  };

  it('sin sesión manda al login con la ruta de regreso', async () => {
    configurar(sesionFalsa(null));
    expect(texto(await correr(sesionGuard))).toBe('/login?volver=%2Falertas');
  });

  it('con sesión deja pasar', async () => {
    configurar(sesionFalsa());
    expect(await correr(sesionGuard)).toBe(true);
  });

  it('sin el permiso regresa al panel', async () => {
    configurar(sesionFalsa(usuarioSesion({ rol: 'operador' }, ['ver_panel'])));
    expect(texto(await correr(permisoGuard('administrar_usuarios')))).toBe('/');
  });

  it('al regresar al panel corrige también la barra de direcciones', async () => {
    configurar(sesionFalsa(usuarioSesion({ rol: 'operador' }, ['ver_panel'])));
    const resultado = (await correr(permisoGuard('consultar_bitacora'))) as RedirectCommand;
    expect(resultado.navigationBehaviorOptions).toEqual({
      onSameUrlNavigation: 'reload',
      replaceUrl: true,
    });
  });

  it('basta con uno de los permisos pedidos', async () => {
    configurar(sesionFalsa(usuarioSesion({ rol: 'tecnico' }, ['gestionar_nodos'])));
    expect(await correr(permisoGuard('configurar_cultivos', 'gestionar_nodos'))).toBe(true);
  });
});
