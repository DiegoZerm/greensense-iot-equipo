import { HttpClient, HttpResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { Agregado, Resumen, SerieLecturas } from './modelos';

export type Periodo = 'hora' | 'dia';

export interface Rango {
  nodo: string;
  desde: string;
  hasta: string;
}

export interface Descarga {
  nombre: string;
  contenido: Blob;
}

/** Consultas del historial y descarga de reportes CSV. */
@Injectable({ providedIn: 'root' })
export class HistorialService {
  private readonly http = inject(HttpClient);

  lecturas(rango: Rango): Observable<SerieLecturas> {
    return this.http.get<SerieLecturas>('/api/v1/lecturas', { params: { ...rango } });
  }

  agregadas(rango: Rango, periodo: Periodo): Observable<Agregado[]> {
    return this.http.get<Agregado[]>('/api/v1/lecturas/agregadas', {
      params: { ...rango, periodo },
    });
  }

  resumen(rango: Rango): Observable<Resumen> {
    return this.http.get<Resumen>('/api/v1/reportes/resumen', { params: { ...rango } });
  }

  /** `tipo` lecturas exige nodo; alertas lo toma como filtro. */
  descargar(tipo: 'lecturas' | 'alertas', rango: Rango): Observable<Descarga> {
    return this.http
      .get(`/api/v1/reportes/${tipo}.csv`, {
        params: { ...rango },
        responseType: 'blob',
        observe: 'response',
      })
      .pipe(map((respuesta) => aDescarga(respuesta, `${tipo}.csv`)));
  }
}

function aDescarga(respuesta: HttpResponse<Blob>, porDefecto: string): Descarga {
  const disposicion = respuesta.headers.get('Content-Disposition') ?? '';
  const nombre = /filename="([^"]+)"/.exec(disposicion)?.[1] ?? porDefecto;
  return { nombre, contenido: respuesta.body ?? new Blob() };
}

/** Guarda el archivo con el diálogo de descarga del navegador. */
export function guardarArchivo({ nombre, contenido }: Descarga): void {
  const url = URL.createObjectURL(contenido);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
