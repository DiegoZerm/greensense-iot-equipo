import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { CanActivateFn, RedirectCommand, Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { Permiso } from './modelos';
import { SesionService } from './sesion.service';

/** Agrega el token a las peticiones de la API y cierra la sesión si el servidor la rechaza. */
export const autenticacionInterceptor: HttpInterceptorFn = (peticion, siguiente) => {
  const sesion = inject(SesionService);
  const token = sesion.token();
  const aLaApi = peticion.url.startsWith('/api/');
  const conToken =
    token && aLaApi
      ? peticion.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : peticion;
  return siguiente(conToken).pipe(
    catchError((error: unknown) => {
      const esLogin = peticion.url.endsWith('/auth/login');
      if (error instanceof HttpErrorResponse && error.status === 401 && aLaApi && !esLogin) {
        sesion.expirar();
      }
      return throwError(() => error);
    }),
  );
};

/** Exige sesión; si no hay, manda al login y regresa después a donde iba. */
export const sesionGuard: CanActivateFn = async (_, estado) => {
  const sesion = inject(SesionService);
  const router = inject(Router);
  if (sesion.iniciada() || (await sesion.comprobar())) {
    return true;
  }
  return router.createUrlTree(['/login'], { queryParams: { volver: estado.url } });
};

/** Exige un permiso del rol del usuario; sin él, regresa al panel. */
export function permisoGuard(...permisos: Permiso[]): CanActivateFn {
  return async () => {
    const sesion = inject(SesionService);
    const router = inject(Router);
    if (!sesion.iniciada() && !(await sesion.comprobar())) {
      return router.createUrlTree(['/login']);
    }
    if (permisos.some((p) => sesion.puede(p))) {
      return true;
    }
    // Al abrir la app directo en una ruta prohibida, el router todavía cree estar en "/" e
    // ignoraría la redirección por ser la misma URL: se pide recargar de todos modos.
    return new RedirectCommand(router.parseUrl('/'), { onSameUrlNavigation: 'reload' });
  };
}

/** Mensaje legible de un error de la API: el `detail` del servidor o uno genérico. */
export function mensajeDeError(
  error: unknown,
  generico = 'No se pudo completar la operación',
): string {
  if (error instanceof HttpErrorResponse) {
    const detalle = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detalle === 'string') {
      return capitalizar(detalle);
    }
    if (Array.isArray(detalle) && detalle.length) {
      // Errores de validación de FastAPI: [{loc, msg}, ...]
      return detalle.map((d: { msg?: string }) => d.msg ?? '').join('. ');
    }
    if (error.status === 0) {
      return 'No hay conexión con el servidor';
    }
  }
  return generico;
}

function capitalizar(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
