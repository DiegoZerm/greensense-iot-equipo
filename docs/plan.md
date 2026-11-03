# Plan de estructura del código

Este plan define cómo se organiza el código de GreenSense IoT. Se basa en la propuesta del proyecto (arquitectura, tecnologías, modelo de datos y producto mínimo) y en la conclusión de la actividad de diseño: el servidor usa **puertos y adaptadores**, y las reglas son implementaciones intercambiables de una interfaz.

## 1. Vista general

```
Nodo ESP32 ──MQTT──> Mosquitto ──> Servidor FastAPI ──API/SSE──> PWA Angular
 DHT22                (tema por nodo)   reglas, alertas,              panel, gráficas,
 suelo capacitivo                       PostgreSQL + Timescale        alertas, config.
                                              │
                                              └──Web Push──> teléfono
```

Es un monorepo con una carpeta por componente, de modo que cada parte se puede desarrollar, probar y asignar por separado.

```
greensense-iot/
├── firmware/      nodo ESP32 (PlatformIO, framework Arduino)
├── servidor/      API y procesamiento (Python, FastAPI)
├── app/           aplicación web progresiva (Angular)
├── analisis/      estadística y regresión lineal (pandas, scikit-learn)
├── infra/         docker compose: Mosquitto, PostgreSQL/TimescaleDB, servidor, app
├── docs/          arquitectura, contrato MQTT, API, modelo de datos, manuales
└── .github/       integración continua
```

## 2. Contrato MQTT (lo que une al nodo con el servidor)

Se define antes que el código, porque firmware y servidor dependen de él.

| Tema | Dirección | Contenido |
|---|---|---|
| `greensense/{invernadero}/{nodo}/lecturas` | nodo → servidor | lectura en JSON, QoS 1 |
| `greensense/{invernadero}/{nodo}/estado` | nodo → servidor | `conectado` / `desconectado` (mensaje de última voluntad, retenido) |
| `greensense/{invernadero}/{nodo}/comandos` | servidor → nodo | reservado para la etapa de actuadores |

El detalle completo está en [`contrato-mqtt.md`](contrato-mqtt.md) y los esquemas en [`contrato/`](contrato).

- Cada lectura se identifica por `(nodo, arranque, seq)`. `arranque` cuenta los encendidos del nodo y `seq` es el consecutivo dentro del arranque. Con eso se cuentan las lecturas perdidas (indicador de éxito: menos de 5 %) y se descartan duplicados cuando el nodo reenvía lecturas guardadas sin conexión.
- `ts` viene del nodo (hora por NTP), así que una lectura reenviada conserva su hora real.
- Una variable vale `null` si el nodo no tiene ese sensor o la lectura falló. El nodo nunca inventa valores.
- Cada nodo tiene su propio usuario en Mosquitto y una ACL que solo le permite publicar en sus temas. El servidor además comprueba que el nodo del tema coincida con el del mensaje y que esté registrado.

## 3. Firmware (`firmware/`)

```
firmware/
├── platformio.ini            entornos esp32dev y native (pruebas en la PC)
├── include/config_nodo.example.h  WiFi, broker, nodo y sensores (config_nodo.h no se sube)
├── src/main.cpp              sensores, WiFi, NTP y MQTT
├── lib/nucleo/               lógica sin hardware: filtro (mediana), calibración del suelo,
│                             cola con confirmación, mensajes JSON, hora diferida y LED
└── test/                     pruebas Unity de lib/nucleo (entorno native)
```

El cliente MQTT es el de ESP-IDF (`esp-mqtt`), incluido en el framework, porque publica con QoS 1 y avisa cuando el broker confirma cada mensaje. PubSubClient solo publica con QoS 0. La cola vive en RAM: soporta caídas de WiFi o del broker de hasta 12 horas, pero no un corte de energía, que de todos modos apaga el nodo.

Hardware disponible: ESP32 DevKit (`esp32dev`) y DHT11. El sensor de suelo todavía no está, así que es opcional desde la configuración. Sin él, el nodo manda `humedad_sustrato: null`, y las reglas de sustrato se prueban con el simulador. El DHT11 mide de 20 a 90 % HR con ±5 %, y el rango del cultivo (60 a 80 %) queda cerca de su límite: es suficiente para el prototipo, pero se menciona en el reporte.

Las piezas sin hardware (filtro, mensaje, cola) quedan separadas de la lectura de sensores para que puedan probarse en la computadora.

## 4. Servidor (`servidor/`)

Toma como base la versión de puertos y adaptadores de `greensense-diseno`, pero con las tecnologías reales.

```
servidor/
├── pyproject.toml
├── greensense/
│   ├── dominio/                  sin dependencias externas
│   │   ├── modelos.py            Lectura, Nodo, Invernadero, Cultivo, Umbral, Alerta, Usuario
│   │   ├── validacion.py         campos requeridos y rangos físicos posibles
│   │   ├── permisos.py           roles y matriz de permisos de la propuesta
│   │   └── reglas/
│   │       ├── base.py           interfaz ReglaAlerta
│   │       ├── umbral.py         advertencia y crítico con tiempo mínimo
│   │       ├── sustrato_alto.py  humedad alta sostenida (pudrición de raíz)
│   │       ├── riesgo_hongos.py  humedad relativa y temperatura altas a la vez
│   │       └── lectura_imposible.py
│   ├── aplicacion/
│   │   ├── puertos.py            repositorios, Notificador, Reloj, Bitacora, PublicadorTiempoReal
│   │   └── casos_uso/            registrar_lectura, revisar_nodos, atender_alerta,
│   │                             consultar_historico, generar_reporte, configurar_umbrales,
│   │                             gestionar_nodos, gestionar_usuarios, autenticar
│   ├── adaptadores/
│   │   ├── entrada/
│   │   │   ├── mqtt.py           suscriptor (aiomqtt) → registrar_lectura
│   │   │   ├── api/              routers FastAPI por recurso + SSE de tiempo real
│   │   │   └── tareas.py         revisión periódica de nodos desconectados y reintentos de push
│   │   └── salida/
│   │       ├── postgres/         SQLAlchemy 2, un repositorio por entidad
│   │       ├── memoria/          repositorios en memoria para pruebas
│   │       ├── webpush.py        pywebpush con claves VAPID
│   │       └── reloj.py
│   ├── config.py                 pydantic-settings, lee .env
│   └── composicion.py            único lugar donde se eligen las clases concretas
├── migraciones/                  Alembic
├── simulador/                    publica lecturas falsas por MQTT (sirve para trabajar sin el nodo)
└── tests/
    ├── dominio/                  reglas y validación
    ├── casos_uso/                con adaptadores en memoria y reloj falso
    ├── contrato/                 la misma prueba para el repositorio en memoria y el de Postgres
    └── integracion/              Postgres y Mosquitto reales en docker
```

Decisiones:

- **La alerta se guarda antes de notificar.** Si falla el push, la alerta queda pendiente y una tarea la reintenta. Así se corrige el error del diseño original, donde la alerta crítica se perdía.
- **Tiempo real con SSE** (eventos enviados por el servidor) en lugar de WebSocket: el flujo va en una sola dirección y es más simple. Meta: la lectura aparece en el panel en menos de 10 s.
- **Autenticación con JWT** y contraseñas con Argon2. Cada ruta declara el permiso que exige (`requiere_permiso("exportar_reportes")`), siguiendo la matriz de la propuesta.
- **Base de datos:** PostgreSQL con TimescaleDB. `lectura` es una hypertable con restricción única en `(nodo_id, arranque, seq)`. Los promedios por hora y por día se calculan con `time_bucket` sobre la hypertable. Al principio se planearon agregados continuos, pero no muestran las lecturas que el nodo reenvía tarde hasta su siguiente refresco; medido con un año de datos, agrupar directo tarda 70 ms por semana y 240 ms por mes (detalle en `servidor/README.md`).

Tablas: `invernadero`, `cultivo`, `umbral` (cultivo, variable, nivel, mínimo, máximo, tiempo mínimo), `nodo`, `lectura`, `alerta`, `usuario`, `suscripcion_push`, `bitacora`.

Rutas principales de la API (`/api/v1`):

| Recurso | Rutas |
|---|---|
| auth | `POST /auth/login`, `GET /auth/yo`, `PUT /auth/yo/contrasena` |
| lecturas | `GET /lecturas?nodo&desde&hasta`, `GET /lecturas/ultimas`, `GET /lecturas/agregadas?periodo=hora\|dia` (la app filtra por variable) |
| tiempo real | `GET /eventos` (SSE) |
| alertas | `GET /alertas?severidad&variable&desde&hasta`, `POST /alertas/{id}/atender` |
| invernaderos | `GET`, `POST`, `PATCH` y `DELETE /invernaderos` |
| nodos | `GET`, `POST` y `PATCH /nodos` (la baja es `activo: false`) |
| cultivos y umbrales | `GET`, `POST`, `PUT` y `DELETE /cultivos`; el `PUT` reemplaza umbrales y riesgo de hongos |
| usuarios | `GET`, `POST` y `PATCH /usuarios` (solo administrador; se desactivan, no se borran) |
| reportes | `GET /reportes/lecturas.csv`, `GET /reportes/alertas.csv`, `GET /reportes/resumen` |
| push | `GET /push/clave-publica`, `POST /push/suscripciones` |
| bitácora | `GET /bitacora` |

## 5. Aplicación web (`app/`)

Angular con componentes standalone, `@angular/pwa` para instalarla y `SwPush` para las notificaciones. Está diseñada primero para el teléfono.

```
app/src/app/
├── core/          servicio de autenticación, interceptor JWT, guards por rol, cliente de la API, push, SSE
├── shared/        indicador de color, tarjeta de variable, gráfica con líneas de umbral, filtros de fecha
└── features/
    ├── login/
    ├── panel/          valor actual, color, gráfica de las últimas horas, estado del nodo
    ├── historico/      tabla filtrable y exportación a CSV
    ├── graficas/       día, semana o mes con los umbrales como referencia
    ├── alertas/        historial y botón para marcar como atendida
    ├── nodos/
    ├── configuracion/  cultivos, umbrales y usuarios
    └── reportes/
```

Las rutas se cargan bajo demanda, y los guards ocultan las vistas que el rol no tiene permitidas.

## 6. Análisis de datos (`analisis/`)

```
analisis/
├── extraer.py                    exporta lecturas de la base de datos a CSV o Parquet
├── 01_descriptivo.ipynb          promedios, máximos, mínimos y ciclo diario
├── 02_anomalias.ipynb            lecturas fuera del comportamiento habitual
└── 03_regresion_sustrato.ipynb   regresión lineal múltiple: humedad del sustrato a partir de
                                  lecturas anteriores, temperatura y hora del día
```

Se necesitan al menos 7 días de datos reales, así que **el nodo debe empezar a medir lo antes posible**, aunque el resto del sistema no esté terminado.

## 7. Infraestructura (`infra/`)

- `docker-compose.yml` con `mosquitto`, `db` (timescale/timescaledb), `servidor` y `app` (nginx con el build de Angular).
- `mosquitto/mosquitto.conf`, archivo de contraseñas y ACL por nodo.
- `.env.example` con todas las variables. Los `.env` reales y las claves VAPID no se suben.

## 8. Calidad y flujo de trabajo

- GitFlow igual que en los otros repos: `feature/<tema>` → `develop` → `main`. Los commits llevan los prefijos `feat:`, `fix:`, `test:`, `docs:`, `refactor:` y `chore:`.
- Integración continua en GitHub Actions:
  - servidor: `ruff` y `pytest` con cobertura;
  - firmware: `pio test -e native` y `pio run`;
  - app: `ng test` y `ng build`.
- Nombres de código en español, como en `greensense-diseno`.

## 9. Orden de construcción

| Fase | Resultado | Cómo se verifica |
|---|---|---|
| 0. Base | estructura, docker compose, contrato MQTT, CI | `docker compose up` levanta Mosquitto y Postgres, y la CI pasa |
| 1. Tubería de punta a punta | simulador → Mosquitto → servidor → BD → `GET /lecturas/ultimas` → panel mínimo | la lectura simulada aparece en el navegador |
| 2. Nodo real | firmware con sensores, calibración, cola sin conexión y LEDs | el nodo publica sin parar; **empieza la recolección de 7 días** |
| 3. Alertas | reglas, desconexión, Web Push con reintentos | una condición simulada llega al teléfono en menos de 1 min |
| 4. Usuarios y configuración | login, roles, umbrales, cultivos, nodos, bitácora | cada rol solo ve y hace lo de la matriz |
| 5. Consulta | históricos, gráficas, reportes CSV, PWA instalable | se puede reconstruir cualquier día del periodo de prueba |
| 6. Análisis | notebooks descriptivo y de regresión | resultado interpretable con datos propios |
| 7. Cierre | pruebas contra los indicadores de éxito, manuales de instalación y uso | checklist de la propuesta completo |

Las fases 2 y 3 pueden avanzar en paralelo, porque el simulador reemplaza al nodo mientras se desarrolla el servidor.

## 10. Reparto futuro

Cuando se sumen los compañeros, la división natural es por carpeta (firmware, servidor, app, análisis). Cada carpeta tiene sus propias pruebas y el contrato MQTT y la API ya están fijados, así que se puede trabajar en paralelo sin bloquearse.
