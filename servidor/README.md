# Servidor

API y procesamiento de GreenSense IoT, con FastAPI y una arquitectura de puertos y adaptadores.

```
greensense/
├── dominio/        modelos y validación, sin dependencias externas
├── aplicacion/     casos de uso y puertos
├── adaptadores/
│   ├── entrada/    API HTTP (REST y SSE) y recepción MQTT
│   └── salida/     PostgreSQL, memoria, eventos en tiempo real y reloj
├── contenedor.py   casos de uso ya armados
├── composicion.py  único lugar donde se eligen las clases concretas
├── config.py       lee variables de entorno o infra/.env
└── cli.py          comando greensense
migraciones/        Alembic
simulador/          nodos simulados que publican por MQTT
```

## Preparación

```bash
cd servidor
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Con la infraestructura levantada (ver [`infra/`](../infra)):

```bash
.venv/bin/greensense migrar
.venv/bin/greensense invernadero agregar invernadero1 "Invernadero de prueba"
.venv/bin/greensense nodo agregar invernadero1 nodo1 "Nodo 1" --sensor-aire DHT11
.venv/bin/greensense nodo listar
.venv/bin/greensense usuario agregar ana@ejemplo.com "Ana López" --rol administrador
```

Cada nodo necesita además su usuario MQTT en `MQTT_NODOS` de `infra/.env`.

El primer administrador también se puede crear solo: si la base no tiene usuarios, el servidor crea al arrancar el de `ADMIN_CORREO` y `ADMIN_CONTRASENA` de `infra/.env`. Los demás usuarios, cultivos, invernaderos y nodos se administran desde la app.

## Correr

```bash
.venv/bin/uvicorn --factory greensense.composicion:crear_aplicacion --reload
```

Todas las rutas piden sesión (`Authorization: Bearer <token>`) salvo `salud`, `auth/login` y `push/clave-publica`. Entre paréntesis, el permiso que exigen.

| Ruta | Qué hace |
|---|---|
| `GET /salud` | Estado y versión |
| `POST /auth/login`, `GET /auth/yo`, `PUT /auth/yo/contrasena` | Iniciar sesión (devuelve el token y los permisos), usuario actual y cambio de la contraseña propia |
| `GET /lecturas/ultimas` (ver_panel) | Cada nodo activo con su lectura más reciente y sus alertas activas |
| `GET /eventos?token=` (ver_panel) | Flujo SSE con los eventos `lectura`, `nodo` y `alerta`. El token va en la URL porque EventSource no manda encabezados |
| `GET /alertas?activas&limite` (ver_panel), `POST /alertas/{id}/atender` (atender_alertas) | Historial; al atender se guarda quién lo hizo |
| `GET /push/clave-publica`, `POST` y `DELETE /push/suscripciones` | Notificaciones. Cada suscripción es del usuario de la sesión |
| `GET /cultivos` (ver_panel); `POST`, `PUT /{id}` y `DELETE /{id}` (configurar_cultivos) | Cultivos con sus umbrales y riesgo de hongos |
| `GET /invernaderos` (ver_panel); `POST`, `PATCH /{id}` y `DELETE /{id}` (configurar_cultivos) | Un invernadero con nodos no se puede borrar |
| `GET /nodos` (ver_panel); `POST` y `PATCH /{id}` (gestionar_nodos) | Con `{"activo": false}` el nodo se da de baja |
| `GET`, `POST` y `PATCH /usuarios/{id}` (administrar_usuarios) | Los usuarios no se borran, se desactivan |
| `GET /bitacora?limite&antes_de` (consultar_bitacora) | Altas, bajas, cambios de configuración, exportaciones e inicios de sesión |
| `GET /lecturas?nodo&desde&hasta` (consultar_historial) | Lecturas en orden, hasta 20 000; con `completa: false` el rango se recortó |
| `GET /lecturas/agregadas?nodo&desde&hasta&periodo=hora\|dia` (consultar_historial) | Mínimo, máximo y promedio por hora o por día, con los cortes en hora de México |
| `GET /reportes/resumen?nodo&desde&hasta` (consultar_historial) | Estadísticas del rango y lecturas esperadas contra recibidas |
| `GET /reportes/lecturas.csv` y `/reportes/alertas.csv` (exportar_reportes) | Descarga en CSV, en hora local y con marca BOM para Excel. Queda en la bitácora |

Las fechas `desde` y `hasta` van en ISO 8601 con zona (`2026-11-02T00:00:00-06:00`); `desde` se incluye y `hasta` no. El rango máximo es de un año.

Documentación interactiva en http://localhost:8000/docs (botón *Authorize* con el token de `auth/login`).

Para correrlo sin base de datos ni broker: `ALMACENAMIENTO=memoria MQTT_HABILITADO=false`, más `ADMIN_CORREO` y `ADMIN_CONTRASENA` para tener con quién entrar.

## Usuarios y permisos

| Permiso | Operador | Supervisor | Técnico | Administrador |
|---|:-:|:-:|:-:|:-:|
| Ver el panel, el historial y atender alertas | Sí | Sí | Sí | Sí |
| Notificaciones de cultivo (umbrales y hongos) | Sí | Sí | No | Sí |
| Notificaciones de dispositivo (sensor y desconexión) | No | No | Sí | Sí |
| Exportar reportes | No | Sí | No | Sí |
| Registrar y mantener nodos | No | No | Sí | Sí |
| Configurar cultivos, umbrales e invernaderos | No | No | No | Sí |
| Administrar usuarios | No | No | No | Sí |
| Consultar la bitácora | No | Sí | No | Sí |

- Contraseñas con Argon2id; sesiones con JWT firmado con `JWT_SECRETO`, que duran `SESION_HORAS` (12 por defecto).
- El usuario se lee de la base en cada petición: si se le desactiva o se le cambia el rol, aplica de inmediato.
- Siempre debe quedar al menos un administrador activo.

Para correrlo sin base de datos ni broker: `ALMACENAMIENTO=memoria MQTT_HABILITADO=false`.

## Historial

Los agregados se calculan con `time_bucket` directo sobre la hypertable `lectura`, y no con agregados continuos de TimescaleDB. Un agregado continuo no muestra las lecturas que llegan tarde con hora vieja (la cola que el nodo vacía al reconectarse) hasta su siguiente refresco, y la gráfica de esa noche saldría vacía un rato. Con un año de lecturas de un nodo (525 600), una semana por hora tarda unos 70 ms y un mes por día unos 240 ms. Si algún día hay muchos nodos o se consultan años completos, conviene volver a evaluarlos.

Las lecturas esperadas del resumen se cuentan desde la primera lectura del nodo y hasta ahora, según su periodo. Es el dato del indicador de lecturas perdidas de la propuesta.

## Alertas

Cada lectura nueva se evalúa con las reglas del nodo y con los umbrales del cultivo de su invernadero. El cultivo predeterminado es "Hortalizas de hoja", con los rangos de la propuesta.

| Regla | Advertencia | Crítica |
|---|---|---|
| Umbral de temperatura, humedad del aire y del sustrato | Dentro del rango, pero a menos del margen de un límite | Fuera del rango durante el tiempo mínimo (5 min; 3 h para el sustrato alto) |
| Riesgo de hongos | Humedad ≥ 85 % y temperatura ≥ 20 °C | La condición se mantiene 1 h |
| Falla de sensor | El sensor no entrega datos o da un valor imposible | Se mantiene 15 min |
| Desconexión | — | Sin lecturas durante 5 min o 3 periodos, lo que sea mayor |

- Hay una sola alerta activa por nodo, regla y variable. Se actualiza mientras dura el problema y se resuelve sola cuando el valor vuelve a la normalidad.
- Una alerta de umbral se resuelve hasta que el valor se aleja del margen otro medio margen (histéresis): con la temperatura de 18 a 28 °C y margen 2, una advertencia abierta a 26.3 °C se cierra hasta bajar de 25 °C. Sin esto, un valor que oscila en el borde abría y cerraba una advertencia en cada lectura: la demostración pasó de 2455 alertas en una semana a 24.
- Las lecturas con más de 10 minutos de antigüedad (reenvíos del nodo) se guardan, pero no generan alertas.
- Las alertas críticas y las desconexiones se notifican por push a las suscripciones de los usuarios cuyo rol debe recibirlas (ver la tabla de permisos). Si el usuario se desactiva o cambia de rol, sus envíos pendientes se descartan. Cada envío se reintenta con espera creciente (30 s, 1, 2, 4 y 8 min). Las suscripciones vencidas se borran.

Las notificaciones necesitan claves VAPID en `infra/.env`:

```bash
.venv/bin/greensense vapid >> ../infra/.env
```

## Simulador

Publica lecturas como si fuera un nodo, con ciclo de día y noche y riego.

```bash
.venv/bin/gs-simulador --nodo nodo1 --contrasena <clave MQTT> --periodo 5
.venv/bin/gs-simulador --nodo nodo1 --contrasena <clave> --escenario calor   # normal, calor, seco, hongos
.venv/bin/gs-simulador --nodo nodo1 --contrasena <clave> --sensor-aire DHT11 --sin-suelo
.venv/bin/gs-simulador --nodo nodo1 --contrasena <clave> --historico 48      # 48 h de datos y termina
.venv/bin/gs-simulador --nodo nodo1 --contrasena <clave> --forzar temperatura=31   # condición fuera de rango
```

## Datos de demostración

`gs-demo` llena una base aparte (`greensense_demo`) con una semana inventada y sirve la API en el puerto 8001, con lecturas nuevas cada 15 s. No usa MQTT ni toca la base de los datos reales. Los días se simulan con los mismos casos de uso del servidor y un reloj que avanza minuto a minuto, así que las alertas, la bitácora y los resúmenes salen de las reglas reales.

```bash
.venv/bin/gs-demo              # la primera vez genera 7 días (unos 10 min); después se pone al día
.venv/bin/gs-demo --regenerar  # borra la base de demostración y la genera otra vez
cd ../app && npm run demo      # http://localhost:4201, la app conectada a la demostración
```

Usuarios, todos con la contraseña `demo12345`: `ana@greensense.local` (administradora), `bruno@` (supervisor), `carla@` (técnica) y `daniel@` (operador). `practicante@` está desactivado.

| Nodo | Qué prueba |
|---|---|
| `norte/lechuga-1` | Riego fallido hace 5 días (sustrato bajo, crítica atendida); ahora la humedad del aire cerca del máximo (advertencia activa) |
| `norte/espinaca-1` | DHT11 sin sensor de suelo (enteros, sin reglas de sustrato); una noche con riesgo de hongos hace 3 días |
| `norte/semillero` | 4 h sin corriente hace 2 días (desconexión y arranque nuevo); ahora desconectado |
| `sur/tomate-1` | Cultivo "Tomate" con sus propios umbrales; calor hace 4 días y ahora (crítica activa) |
| `sur/tomate-2` | Falla del sensor de aire hace 6 días, valores imposibles sueltos y ahora sustrato encharcado (advertencia que espera 3 h) |
| `sur/prueba-1` | Dado de baja hace 3 días: no sale en el panel, pero conserva su historial |

## Pruebas

```bash
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Las pruebas de `tests/contrato` verifican dos cosas:
- que los mensajes MQTT coincidan con [`docs/contrato`](../docs/contrato);
- que los repositorios en memoria y los de PostgreSQL se comporten igual.

Las de PostgreSQL corren si `GREENSENSE_PRUEBAS_DB` apunta a una base de datos de pruebas, que se borra al empezar:

```bash
docker compose -f ../infra/docker-compose.yml exec db psql -U greensense -c "CREATE DATABASE greensense_pruebas"
export GREENSENSE_PRUEBAS_DB=postgresql+psycopg://greensense:<clave>@localhost:5432/greensense_pruebas
```
