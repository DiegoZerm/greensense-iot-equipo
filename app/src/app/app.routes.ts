import { Routes } from '@angular/router';
import { permisoGuard, sesionGuard } from './core/autenticacion';

export const routes: Routes = [
  {
    path: 'login',
    title: 'Iniciar sesión · GreenSense',
    loadComponent: () => import('./features/login/login').then((m) => m.Login),
  },
  {
    path: '',
    canActivate: [sesionGuard],
    children: [
      {
        path: '',
        title: 'Panel · GreenSense',
        loadComponent: () => import('./features/panel/panel').then((m) => m.Panel),
      },
      {
        path: 'alertas',
        title: 'Alertas · GreenSense',
        loadComponent: () => import('./features/alertas/alertas').then((m) => m.Alertas),
      },
      {
        path: 'historial',
        title: 'Historial · GreenSense',
        canActivate: [permisoGuard('consultar_historial')],
        loadComponent: () => import('./features/historial/historial').then((m) => m.Historial),
      },
      {
        path: 'configuracion',
        canActivate: [
          permisoGuard('configurar_cultivos', 'gestionar_nodos', 'administrar_usuarios'),
        ],
        loadChildren: () =>
          import('./features/configuracion/configuracion.routes').then((m) => m.rutas),
      },
      {
        path: 'bitacora',
        title: 'Bitácora · GreenSense',
        canActivate: [permisoGuard('consultar_bitacora')],
        loadComponent: () => import('./features/bitacora/bitacora').then((m) => m.Bitacora),
      },
      {
        path: 'cuenta',
        title: 'Mi cuenta · GreenSense',
        loadComponent: () => import('./features/cuenta/cuenta').then((m) => m.Cuenta),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
