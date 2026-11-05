import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { mensajeDeError } from '../../core/autenticacion';
import { ConfiguracionService } from '../../core/configuracion.service';
import { RegistroBitacora } from '../../core/modelos';

const ACCIONES: Record<string, string> = {
  iniciar_sesion: 'Inició sesión',
  crear: 'Creó',
  modificar: 'Modificó',
  borrar: 'Borró',
  alta: 'Dio de alta',
  baja: 'Dio de baja',
  exportar: 'Exportó',
};

const OBJETOS: Record<string, string> = {
  usuario: 'usuario',
  cultivo: 'cultivo',
  invernadero: 'invernadero',
  nodo: 'nodo',
  reporte: 'reporte',
};

@Component({
  selector: 'gs-bitacora',
  imports: [DatePipe],
  template: `
    <h2>Bitácora</h2>
    <p class="gs-nota">Cambios de configuración, altas, bajas e inicios de sesión.</p>
    @if (error(); as e) {
      <p class="gs-aviso" role="alert">{{ e }}</p>
    }
    <div class="gs-desplazable">
      <table class="gs-tabla">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Usuario</th>
            <th>Acción</th>
            <th>Detalle</th>
          </tr>
        </thead>
        <tbody>
          @for (r of registros(); track r.id) {
            <tr [attr.data-registro]="r.id">
              <td>{{ r.ts | date: 'dd/MM/yy HH:mm' }}</td>
              <td>{{ r.usuario_nombre ?? 'Sistema' }}</td>
              <td>{{ accion(r) }}</td>
              <td>{{ r.detalle }}</td>
            </tr>
          } @empty {
            <tr>
              <td colspan="4">Sin registros.</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
    @if (hayMas()) {
      <button class="gs-boton secundario" type="button" (click)="cargar()">Cargar más</button>
    }
  `,
  styles: `
    button {
      margin-top: 0.75rem;
    }
  `,
})
export class Bitacora {
  private readonly configuracion = inject(ConfiguracionService);

  protected readonly registros = signal<RegistroBitacora[]>([]);
  protected readonly hayMas = signal(false);
  protected readonly error = signal<string | null>(null);

  constructor() {
    this.cargar();
  }

  protected cargar(): void {
    const ultimo = this.registros().at(-1)?.id;
    this.configuracion.bitacora(ultimo).subscribe({
      next: (nuevos) => {
        this.registros.update((actuales) => [...actuales, ...nuevos]);
        this.hayMas.set(nuevos.length === 50);
      },
      error: (e) => this.error.set(mensajeDeError(e, 'No se pudo consultar la bitácora')),
    });
  }

  protected accion(r: RegistroBitacora): string {
    const accion = ACCIONES[r.accion] ?? r.accion;
    if (r.accion === 'iniciar_sesion') {
      return accion;
    }
    return `${accion} ${OBJETOS[r.objeto] ?? r.objeto} ${r.objeto_id}`;
  }
}
