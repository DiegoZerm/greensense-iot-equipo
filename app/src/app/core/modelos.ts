// Mismo formato que las respuestas de la API (servidor/greensense/adaptadores/entrada/api/esquemas.py).

export type EstadoNodo = 'desconocido' | 'conectado' | 'desconectado';

export interface Nodo {
  id: string;
  invernadero_id: string;
  nombre: string;
  sensor_aire: string;
  sensor_suelo: boolean;
  estado: EstadoNodo;
  firmware: string | null;
  periodo_s: number;
  ultima_lectura_en: string | null;
  /** false si se dio de baja: conserva su historial pero ya no aparece en el panel. */
  activo: boolean;
}

export interface Lectura {
  ts: string;
  arranque: number;
  seq: number;
  temperatura: number | null;
  humedad_aire: number | null;
  humedad_sustrato: number | null;
  muestras: number | null;
  rssi: number | null;
}

export type TipoAlerta = 'umbral' | 'hongos' | 'sensor' | 'desconexion';
export type Severidad = 'advertencia' | 'critica';

export interface Alerta {
  id: number;
  nodo_id: string;
  tipo: TipoAlerta;
  variable: Variable | null;
  severidad: Severidad;
  mensaje: string;
  recomendacion: string;
  valor: number | null;
  limite: number | null;
  iniciada_en: string;
  actualizada_en: string;
  /** Desde cuándo está fuera de rango; en una desconexión, la hora de la última lectura. */
  fuera_desde: string | null;
  escalada_en: string | null;
  resuelta_en: string | null;
  atendida_en: string | null;
  atendida_por: number | null;
  atendida_por_nombre: string | null;
  activa: boolean;
}

export interface EstadoActual {
  nodo: Nodo;
  ultima: Lectura | null;
  alertas: Alerta[];
}

export type Variable = 'temperatura' | 'humedad_aire' | 'humedad_sustrato';

export const VARIABLES: readonly { clave: Variable; nombre: string; unidad: string }[] = [
  { clave: 'temperatura', nombre: 'Temperatura', unidad: '°C' },
  { clave: 'humedad_aire', nombre: 'Humedad del aire', unidad: '%' },
  { clave: 'humedad_sustrato', nombre: 'Humedad del sustrato', unidad: '%' },
];

// --- Usuarios y permisos (servidor/greensense/dominio/usuarios.py) ---------------------

export type Rol = 'operador' | 'supervisor' | 'tecnico' | 'administrador';

export const ROLES: readonly { clave: Rol; nombre: string }[] = [
  { clave: 'operador', nombre: 'Operador' },
  { clave: 'supervisor', nombre: 'Supervisor' },
  { clave: 'tecnico', nombre: 'Técnico' },
  { clave: 'administrador', nombre: 'Administrador' },
];

export type Permiso =
  | 'ver_panel'
  | 'notificaciones_cultivo'
  | 'notificaciones_dispositivo'
  | 'consultar_historial'
  | 'atender_alertas'
  | 'exportar_reportes'
  | 'gestionar_nodos'
  | 'configurar_cultivos'
  | 'administrar_usuarios'
  | 'consultar_bitacora';

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  rol: Rol;
  activo: boolean;
  creado_en: string;
}

/** El usuario de la sesión, con los permisos que le da su rol. */
export interface UsuarioSesion extends Usuario {
  permisos: Permiso[];
}

// --- Configuración ---------------------------------------------------------------------

export interface Umbral {
  variable: Variable;
  minimo: number;
  maximo: number;
  margen: number;
  tiempo_bajo_s: number;
  tiempo_alto_s: number;
}

export interface Cultivo {
  id: string;
  nombre: string;
  umbrales: Umbral[];
  hongos: { humedad_minima: number; temperatura_minima: number; tiempo_minimo_s: number };
}

export interface Invernadero {
  id: string;
  nombre: string;
  cultivo_id: string;
}

export interface RegistroBitacora {
  id: number;
  ts: string;
  usuario_id: number | null;
  usuario_nombre: string | null;
  accion: string;
  objeto: string;
  objeto_id: string;
  detalle: string;
}

// --- Historial (servidor/greensense/adaptadores/entrada/api/historial.py) ---------------

export interface Estadistica {
  minimo: number;
  maximo: number;
  promedio: number;
  n: number;
}

export type Estadisticas = Record<Variable, Estadistica | null>;

export interface SerieLecturas {
  lecturas: Lectura[];
  /** false si el rango tenía demasiadas lecturas y se recortó. */
  completa: boolean;
}

export interface Agregado {
  inicio: string;
  lecturas: number;
  variables: Estadisticas;
}

export interface Resumen {
  nodo_id: string;
  desde: string;
  hasta: string;
  lecturas: number;
  esperadas: number;
  perdidas: number;
  porcentaje_perdidas: number | null;
  variables: Estadisticas;
}
