import { inject } from '@angular/core';
import { Router, Routes } from '@angular/router';
import { permisoGuard } from '../../core/autenticacion';
import { SesionService } from '../../core/sesion.service';
import { Configuracion, PESTANAS } from './configuracion';

export const rutas: Routes = [
  {
    path: '',
    component: Configuracion,
    children: [
      {
        path: '',
        pathMatch: 'full',
        children: [],
        // Abre la primera pestaña que el rol puede usar.
        canActivate: [
          () => {
            const sesion = inject(SesionService);
            const pestana = PESTANAS.find((p) => sesion.puede(p.permiso));
            return inject(Router).createUrlTree(['/configuracion', pestana?.ruta ?? '']);
          },
        ],
      },
      {
        path: 'cultivos',
        title: 'Cultivos · GreenSense',
        canActivate: [permisoGuard('configurar_cultivos')],
        loadComponent: () => import('./cultivos').then((m) => m.Cultivos),
      },
      {
        path: 'invernaderos',
        title: 'Invernaderos · GreenSense',
        canActivate: [permisoGuard('configurar_cultivos')],
        loadComponent: () => import('./invernaderos').then((m) => m.Invernaderos),
      },
      {
        path: 'nodos',
        title: 'Nodos · GreenSense',
        canActivate: [permisoGuard('gestionar_nodos')],
        loadComponent: () => import('./nodos').then((m) => m.Nodos),
      },
      {
        path: 'usuarios',
        title: 'Usuarios · GreenSense',
        canActivate: [permisoGuard('administrar_usuarios')],
        loadComponent: () => import('./usuarios').then((m) => m.Usuarios),
      },
    ],
  },
];
