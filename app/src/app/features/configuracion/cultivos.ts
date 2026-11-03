import { Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { mensajeDeError } from '../../core/autenticacion';
import { ConfiguracionService } from '../../core/configuracion.service';
import { Cultivo, Umbral, VARIABLES, Variable } from '../../core/modelos';

const PREDETERMINADO = 'hortalizas-hoja';

/** Valores para una variable que el cultivo todavía no tiene. */
const SUGERIDOS: Record<Variable, Umbral> = {
  temperatura: {
    variable: 'temperatura',
    minimo: 18,
    maximo: 28,
    margen: 2,
    tiempo_bajo_s: 300,
    tiempo_alto_s: 300,
  },
  humedad_aire: {
    variable: 'humedad_aire',
    minimo: 60,
    maximo: 80,
    margen: 5,
    tiempo_bajo_s: 300,
    tiempo_alto_s: 300,
  },
  humedad_sustrato: {
    variable: 'humedad_sustrato',
    minimo: 45,
    maximo: 70,
    margen: 5,
    tiempo_bajo_s: 300,
    tiempo_alto_s: 10800,
  },
};

@Component({
  selector: 'gs-cultivos',
  imports: [ReactiveFormsModule],
  templateUrl: './cultivos.html',
  styleUrl: './cultivos.scss',
})
export class Cultivos {
  private readonly configuracion = inject(ConfiguracionService);
  private readonly fb = inject(NonNullableFormBuilder);

  protected readonly variables = VARIABLES;
  protected readonly cultivos = signal<Cultivo[]>([]);
  /** id del cultivo que se edita; null para uno nuevo. */
  protected readonly elegido = signal<string | null>(null);
  protected readonly mensaje = signal<{ texto: string; exito: boolean } | null>(null);

  protected readonly formulario = this.fb.group({
    id: ['', [Validators.required, Validators.pattern(/^[a-z0-9-]{1,32}$/)]],
    nombre: ['', [Validators.required, Validators.maxLength(100)]],
    umbrales: this.fb.array(
      VARIABLES.map(({ clave }) =>
        this.fb.group({
          variable: [clave as Variable],
          activo: [true],
          minimo: [0, Validators.required],
          maximo: [0, Validators.required],
          margen: [0, [Validators.required, Validators.min(0)]],
          tiempo_bajo_min: [5, [Validators.required, Validators.min(0)]],
          tiempo_alto_min: [5, [Validators.required, Validators.min(0)]],
        }),
      ),
    ),
    hongos: this.fb.group({
      humedad_minima: [85, [Validators.required, Validators.min(0), Validators.max(100)]],
      temperatura_minima: [20, Validators.required],
      tiempo_minimo_min: [60, [Validators.required, Validators.min(0)]],
    }),
  });

  constructor() {
    this.cargar(PREDETERMINADO);
  }

  protected get umbrales() {
    return this.formulario.controls.umbrales.controls;
  }

  protected editar(cultivo: Cultivo): void {
    this.elegido.set(cultivo.id);
    this.mensaje.set(null);
    this.formulario.reset({
      id: cultivo.id,
      nombre: cultivo.nombre,
      umbrales: VARIABLES.map(({ clave }) => {
        const umbral = cultivo.umbrales.find((u) => u.variable === clave);
        return aFormulario(umbral ?? SUGERIDOS[clave], umbral !== undefined);
      }),
      hongos: {
        humedad_minima: cultivo.hongos.humedad_minima,
        temperatura_minima: cultivo.hongos.temperatura_minima,
        tiempo_minimo_min: cultivo.hongos.tiempo_minimo_s / 60,
      },
    });
    this.formulario.controls.id.disable();
  }

  protected nuevo(): void {
    this.elegido.set(null);
    this.mensaje.set(null);
    this.formulario.reset({
      id: '',
      nombre: '',
      umbrales: VARIABLES.map(({ clave }) => aFormulario(SUGERIDOS[clave], true)),
      hongos: { humedad_minima: 85, temperatura_minima: 20, tiempo_minimo_min: 60 },
    });
    this.formulario.controls.id.enable();
  }

  protected guardar(): void {
    const datos = this.formulario.getRawValue();
    const cultivo: Cultivo = {
      id: datos.id,
      nombre: datos.nombre,
      umbrales: datos.umbrales
        .filter((u) => u.activo)
        .map((u) => ({
          variable: u.variable,
          minimo: u.minimo,
          maximo: u.maximo,
          margen: u.margen,
          tiempo_bajo_s: Math.round(u.tiempo_bajo_min * 60),
          tiempo_alto_s: Math.round(u.tiempo_alto_min * 60),
        })),
      hongos: {
        humedad_minima: datos.hongos.humedad_minima,
        temperatura_minima: datos.hongos.temperatura_minima,
        tiempo_minimo_s: Math.round(datos.hongos.tiempo_minimo_min * 60),
      },
    };
    const peticion =
      this.elegido() === null
        ? this.configuracion.crearCultivo(cultivo)
        : this.configuracion.guardarCultivo(cultivo);
    peticion.subscribe({
      next: (guardado) => {
        this.cargar(guardado.id);
        this.mensaje.set({
          texto: 'Guardado. Aplica desde la siguiente lectura de cada nodo.',
          exito: true,
        });
      },
      error: (e) => this.mensaje.set({ texto: mensajeDeError(e), exito: false }),
    });
  }

  protected borrar(): void {
    const id = this.elegido();
    if (!id || !confirm(`¿Borrar el cultivo ${id}?`)) {
      return;
    }
    this.configuracion.borrarCultivo(id).subscribe({
      next: () => this.cargar(PREDETERMINADO),
      error: (e) => this.mensaje.set({ texto: mensajeDeError(e), exito: false }),
    });
  }

  protected esPredeterminado(): boolean {
    return this.elegido() === PREDETERMINADO;
  }

  private cargar(editar: string): void {
    this.configuracion.cultivos().subscribe({
      next: (cultivos) => {
        this.cultivos.set(cultivos);
        const cultivo = cultivos.find((c) => c.id === editar) ?? cultivos[0];
        if (cultivo) {
          const mensaje = this.mensaje();
          this.editar(cultivo);
          this.mensaje.set(mensaje);
        }
      },
      error: (e) => this.mensaje.set({ texto: mensajeDeError(e), exito: false }),
    });
  }
}

function aFormulario(umbral: Umbral, activo: boolean) {
  return {
    variable: umbral.variable,
    activo,
    minimo: umbral.minimo,
    maximo: umbral.maximo,
    margen: umbral.margen,
    tiempo_bajo_min: umbral.tiempo_bajo_s / 60,
    tiempo_alto_min: umbral.tiempo_alto_s / 60,
  };
}
