import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Permiso } from '../../core/modelos';
import { SesionService } from '../../core/sesion.service';

export const PESTANAS: readonly { ruta: string; nombre: string; permiso: Permiso }[] = [
  { ruta: 'cultivos', nombre: 'Cultivos y umbrales', permiso: 'configurar_cultivos' },
  { ruta: 'invernaderos', nombre: 'Invernaderos', permiso: 'configurar_cultivos' },
  { ruta: 'nodos', nombre: 'Nodos', permiso: 'gestionar_nodos' },
  { ruta: 'usuarios', nombre: 'Usuarios', permiso: 'administrar_usuarios' },
];

@Component({
  selector: 'gs-configuracion',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <h2>Configuración</h2>
    <nav class="pestanas">
      @for (p of visibles(); track p.ruta) {
        <a [routerLink]="p.ruta" routerLinkActive="activa">{{ p.nombre }}</a>
      }
    </nav>
    <router-outlet />
  `,
  styles: `
    h2 {
      margin-top: 0;
    }
    .pestanas {
      display: flex;
      flex-wrap: wrap;
      gap: 0.25rem;
      margin-bottom: 1rem;
      border-bottom: 2px solid #e0e0e0;
    }
    a {
      padding: 0.4rem 0.8rem;
      color: #444;
      text-decoration: none;
      border-bottom: 3px solid transparent;
      margin-bottom: -2px;
    }
    a.activa {
      color: var(--gs-verde);
      border-bottom-color: var(--gs-verde);
      font-weight: 600;
    }
  `,
})
export class Configuracion {
  private readonly sesion = inject(SesionService);
  protected readonly visibles = computed(() =>
    PESTANAS.filter((p) => this.sesion.puede(p.permiso)),
  );
}
