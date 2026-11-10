# GreenSense IoT

Sistema de monitoreo ambiental y alertas para invernaderos. Un nodo ESP32 mide la temperatura, la humedad del aire y la humedad del sustrato, y publica las lecturas por MQTT. El servidor las valida, las guarda, evalúa los umbrales del cultivo y envía notificaciones push. Una aplicación web progresiva muestra el estado actual, el historial y las alertas.

| Carpeta | Componente | Tecnología |
|---|---|---|
| `firmware/` | Nodo de sensores | ESP32, PlatformIO |
| `servidor/` | API y procesamiento | Python, FastAPI, PostgreSQL/TimescaleDB |
| `app/` | Aplicación web progresiva | Angular |
| `analisis/` | Análisis de datos | pandas, scikit-learn |
| `infra/` | Entorno local | Docker Compose, Mosquitto |

- [Manual de instalación](docs/manual-instalacion.md) y [manual de uso](docs/manual-uso.md).
- La estructura y el orden de construcción están en [`docs/plan.md`](docs/plan.md).

## Probar el sistema completo con el simulador

```bash
# 1. Broker y base de datos
cd infra && cp .env.example .env            # cambiar contraseñas; MQTT_NODOS="nodo1:<clave>"
./mosquitto/crear_usuarios.sh && docker compose up -d && cd ..

# 2. Servidor
cd servidor && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/greensense migrar
.venv/bin/greensense invernadero agregar invernadero1 "Invernadero de prueba"
.venv/bin/greensense nodo agregar invernadero1 nodo1 "Nodo 1" --sensor-suelo
.venv/bin/uvicorn --factory greensense.composicion:crear_aplicacion

# 3. Simulador (otra terminal)
servidor/.venv/bin/gs-simulador --nodo nodo1 --contrasena <clave> --periodo 5

# 4. Panel (otra terminal): http://localhost:4200
cd app && npm ci && npm start
```

Para entrar a la app se usa el administrador de `ADMIN_CORREO` y `ADMIN_CONTRASENA` de `infra/.env`, que el servidor crea la primera vez que arranca. Desde **Configuración** se agregan los demás usuarios con su rol.

