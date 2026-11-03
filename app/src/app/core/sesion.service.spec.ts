import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { autenticacionInterceptor, mensajeDeError } from './autenticacion';
import { usuarioSesion } from './fabricas-pruebas';
import { SesionService } from './sesion.service';
import { HttpErrorResponse } from '@angular/common/http';

describe('SesionService y el interceptor', () => {
  let sesion: SesionService;
  let http: HttpTestingController;
  let cliente: HttpClient;

  function configurar() {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([autenticacionInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    sesion = TestBed.inject(SesionService);
    http = TestBed.inject(HttpTestingController);
    cliente = TestBed.inject(HttpClient);
  }

  beforeEach(() => {
    localStorage.clear();
    configurar();
  });

  afterEach(() => http.verify());

  async function iniciar() {
    const promesa = sesion.iniciar('ana@ejemplo.com', 'secreta123');
    const peticion = http.expectOne('/api/v1/auth/login');
    expect(peticion.request.body).toEqual({ correo: 'ana@ejemplo.com', contrasena: 'secreta123' });
    expect(peticion.request.headers.has('Authorization')).toBe(false);
    peticion.flush({ token: 'jwt-1', usuario: usuarioSesion() });
    await promesa;
  }

  it('inicia sesión, guarda el token y conoce los permisos', async () => {
    await iniciar();

    expect(sesion.iniciada()).toBe(true);
    expect(sesion.token()).toBe('jwt-1');
    expect(localStorage.getItem('greensense.token')).toBe('jwt-1');
    expect(sesion.puede('administrar_usuarios')).toBe(true);
  });

  it('el interceptor agrega el token solo a la API', async () => {
    await iniciar();

    cliente.get('/api/v1/nodos').subscribe();
    cliente.get('/assets/algo.json').subscribe();

    expect(http.expectOne('/api/v1/nodos').request.headers.get('Authorization')).toBe(
      'Bearer jwt-1',
    );
    expect(http.expectOne('/assets/algo.json').request.headers.has('Authorization')).toBe(false);
  });

  it('un 401 cierra la sesión y manda al login', async () => {
    await iniciar();
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);

    const peticion = firstValueFrom(cliente.get('/api/v1/nodos')).catch(() => 'falló');
    http.expectOne('/api/v1/nodos').flush(null, { status: 401, statusText: 'No autorizado' });

    expect(await peticion).toBe('falló');
    expect(sesion.iniciada()).toBe(false);
    expect(localStorage.getItem('greensense.token')).toBeNull();
    expect(navegar).toHaveBeenCalledWith(['/login'], { queryParams: { motivo: 'vencida' } });
  });

  it('un 403 no cierra la sesión', async () => {
    await iniciar();

    cliente.get('/api/v1/usuarios').subscribe({ error: () => undefined });
    http.expectOne('/api/v1/usuarios').flush(null, { status: 403, statusText: 'Prohibido' });

    expect(sesion.iniciada()).toBe(true);
  });

  it('al abrir la app recupera la sesión con el token guardado', async () => {
    localStorage.setItem('greensense.token', 'jwt-guardado');
    TestBed.resetTestingModule();
    configurar();

    const comprobado = sesion.comprobar();
    const otra = sesion.comprobar();
    const peticion = http.expectOne('/api/v1/auth/yo');
    expect(peticion.request.headers.get('Authorization')).toBe('Bearer jwt-guardado');
    peticion.flush(usuarioSesion({ nombre: 'Beto' }));

    expect(await comprobado).toBe(true);
    expect(await otra).toBe(true);
    expect(sesion.usuario()?.nombre).toBe('Beto');
  });

  it('sin token no consulta al servidor', async () => {
    expect(await sesion.comprobar()).toBe(false);
  });

  it('cerrar borra el token', async () => {
    await iniciar();
    sesion.cerrar();

    expect(sesion.token()).toBeNull();
    expect(sesion.puede('ver_panel')).toBe(false);
  });
});

describe('mensajeDeError', () => {
  const error = (status: number, cuerpo: unknown) =>
    new HttpErrorResponse({ status, error: cuerpo });

  it('usa el detalle del servidor', () => {
    expect(mensajeDeError(error(409, { detail: 'ya existe el nodo' }))).toBe('Ya existe el nodo');
  });

  it('junta los errores de validación', () => {
    const detalle = [{ msg: 'campo requerido' }, { msg: 'muy corto' }];
    expect(mensajeDeError(error(422, { detail: detalle }))).toBe('campo requerido. muy corto');
  });

  it('sin conexión o sin detalle', () => {
    expect(mensajeDeError(error(0, null))).toBe('No hay conexión con el servidor');
    expect(mensajeDeError(error(500, null), 'Falló')).toBe('Falló');
  });
});
