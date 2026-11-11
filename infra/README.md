# Infraestructura local

Levanta el broker MQTT (Mosquitto) y la base de datos (PostgreSQL con TimescaleDB).

```bash
cd infra
cp .env.example .env              # cambiar las contraseñas
./mosquitto/crear_usuarios.sh     # genera mosquitto/passwd
docker compose up -d
docker compose ps                 # db debe aparecer como healthy
```

- Mosquitto no acepta conexiones anónimas. Cada nodo se conecta con su identificador como usuario, y la ACL (`mosquitto/acl`) solo le permite publicar en sus propios temas.
- Para agregar un nodo: se añade a `MQTT_NODOS` en `.env`, se vuelve a correr `crear_usuarios.sh` y se reinicia Mosquitto con `docker compose restart mosquitto`.
- Para borrar todos los datos: `docker compose down -v`.

## Desplegar el sistema completo

Con el perfil `app`, el servidor y la app también corren en Docker. nginx sirve la app en el puerto `APP_PUERTO` (8080 por defecto) y manda `/api` al servidor. Las migraciones se aplican solas al arrancar.

```bash
cd infra
docker compose --profile app up -d --build      # http://localhost:8080
docker compose --profile app logs -f servidor
docker compose --profile app down               # conserva los datos
```

Solo debe correr un servidor a la vez: los dos usarían el mismo cliente MQTT y se sacarían mutuamente del broker. Si el servidor corre como servicio de usuario, primero hay que detenerlo con `systemctl --user stop greensense-servidor`.

## HTTPS con un túnel

Las notificaciones push en un teléfono necesitan HTTPS. El perfil `tunel` lo da con [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/), sin abrir puertos del router.

**El túnel publica la app en internet.** Antes de usarlo hay que correr `./revisar_secretos.sh` y cambiar desde la app (**Mi cuenta**) cualquier contraseña de prueba. El script no puede revisar las contraseñas que ya están guardadas en la base.

```bash
./revisar_secretos.sh
docker compose --profile app --profile tunel up -d --build
docker compose --profile app --profile tunel logs tunel | grep -o "https://[a-z0-9-]*\.trycloudflare\.com" | tail -1
```

La dirección cambia cada vez que se reinicia el túnel, y el navegador trata cada una como un sitio distinto: hay que volver a instalar la app y activar las notificaciones. Para apagarlo sin detener lo demás: `docker compose --profile app --profile tunel stop tunel`.

### Probar el push en el teléfono

1. Abrir la dirección pública en el teléfono, entrar y presionar **Activar notificaciones**. En iPhone primero hay que instalar la app en la pantalla de inicio.
2. Provocar una alerta crítica con el simulador. La notificación llega cuando la condición cumple su tiempo mínimo, 5 minutos para la temperatura:

   ```bash
   cd servidor
   .venv/bin/gs-simulador --nodo nodo1 --contrasena <clave> --periodo 10 --forzar temperatura=31
   ```
3. Detener el simulador con Ctrl+C. Si deja de mandar lecturas, el nodo también genera una alerta de desconexión, que le llega a quien tenga el permiso de notificaciones de dispositivo.
