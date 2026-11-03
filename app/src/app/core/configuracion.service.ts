import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Cultivo, Invernadero, Nodo, RegistroBitacora, Rol, Usuario } from './modelos';

export interface NodoNuevo {
  id: string;
  invernadero_id: string;
  nombre: string;
  sensor_aire: string;
  sensor_suelo: boolean;
}

export type CambiosNodo = Partial<Pick<Nodo, 'nombre' | 'sensor_aire' | 'sensor_suelo' | 'activo'>>;

export interface UsuarioNuevo {
  nombre: string;
  correo: string;
  rol: Rol;
  contrasena: string;
}

export type CambiosUsuario = Partial<Pick<Usuario, 'nombre' | 'correo' | 'rol' | 'activo'>> & {
  contrasena?: string;
};

const API = '/api/v1';

/** Llamadas a la API de configuración. Cada pantalla guarda su propio estado. */
@Injectable({ providedIn: 'root' })
export class ConfiguracionService {
  private readonly http = inject(HttpClient);

  cultivos(): Observable<Cultivo[]> {
    return this.http.get<Cultivo[]>(`${API}/cultivos`);
  }

  crearCultivo(cultivo: Cultivo): Observable<Cultivo> {
    return this.http.post<Cultivo>(`${API}/cultivos`, cultivo);
  }

  guardarCultivo({ id, ...datos }: Cultivo): Observable<Cultivo> {
    return this.http.put<Cultivo>(`${API}/cultivos/${id}`, datos);
  }

  borrarCultivo(id: string): Observable<void> {
    return this.http.delete<void>(`${API}/cultivos/${id}`);
  }

  invernaderos(): Observable<Invernadero[]> {
    return this.http.get<Invernadero[]>(`${API}/invernaderos`);
  }

  crearInvernadero(invernadero: Invernadero): Observable<Invernadero> {
    return this.http.post<Invernadero>(`${API}/invernaderos`, invernadero);
  }

  modificarInvernadero(
    id: string,
    cambios: Partial<Omit<Invernadero, 'id'>>,
  ): Observable<Invernadero> {
    return this.http.patch<Invernadero>(`${API}/invernaderos/${id}`, cambios);
  }

  borrarInvernadero(id: string): Observable<void> {
    return this.http.delete<void>(`${API}/invernaderos/${id}`);
  }

  nodos(): Observable<Nodo[]> {
    return this.http.get<Nodo[]>(`${API}/nodos`);
  }

  crearNodo(nodo: NodoNuevo): Observable<Nodo> {
    return this.http.post<Nodo>(`${API}/nodos`, nodo);
  }

  modificarNodo(id: string, cambios: CambiosNodo): Observable<Nodo> {
    return this.http.patch<Nodo>(`${API}/nodos/${id}`, cambios);
  }

  usuarios(): Observable<Usuario[]> {
    return this.http.get<Usuario[]>(`${API}/usuarios`);
  }

  crearUsuario(usuario: UsuarioNuevo): Observable<Usuario> {
    return this.http.post<Usuario>(`${API}/usuarios`, usuario);
  }

  modificarUsuario(id: number, cambios: CambiosUsuario): Observable<Usuario> {
    return this.http.patch<Usuario>(`${API}/usuarios/${id}`, cambios);
  }

  bitacora(antesDe?: number): Observable<RegistroBitacora[]> {
    const params: Record<string, number> = { limite: 50 };
    if (antesDe !== undefined) {
      params['antes_de'] = antesDe;
    }
    return this.http.get<RegistroBitacora[]>(`${API}/bitacora`, { params });
  }

  cambiarMiContrasena(actual: string, nueva: string): Observable<void> {
    return this.http.put<void>(`${API}/auth/yo/contrasena`, { actual, nueva });
  }
}
