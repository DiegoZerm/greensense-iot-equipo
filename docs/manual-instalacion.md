# Manual de instalación

Cómo poner a funcionar GreenSense IoT desde cero: el broker y la base de datos, el servidor, la app y un nodo ESP32. Los detalles de cada parte están en el README de su carpeta.

## 1. Lo que se necesita

| Para | Se necesita |
|---|---|
| Servidor y app | Una computadora con Docker y Docker Compose, encendida al menos una vez cada 24 horas |
| Nodo | ESP32 DevKit, sensor DHT22 o DHT11, sensor capacitivo de suelo (opcional), cargador de celular y cables |
| Cargar el firmware | [PlatformIO](https://platformio.org/install/cli) y un cable USB de datos, no solo de carga |
| Red | Un WiFi de **2.4 GHz** al que se conecten el nodo y la computadora; el ESP32 no usa 5 GHz |
| Notificaciones en el teléfono | Conexión a internet para el túnel HTTPS (sección 6) |

## 2. Configurar los secretos

```bash
git clone <dirección del repositorio>
cd <carpeta del repositorio>/infra
cp .env.example .env
```

Edita `infra/.env`:

- Cambia todas las contraseñas (`DB_CONTRASENA`, `MQTT_CONTRASENA_SERVIDOR` y `ADMIN_CONTRASENA`).
- En `MQTT_NODOS`, deja un par `<nodo>:<contraseña>` por cada nodo; por ejemplo, `MQTT_NODOS="maceta1:una-contraseña-larga"`.
- Genera `JWT_SECRETO`:

  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

Las claves VAPID de las notificaciones se generan en la sección 3. `infra/.env` no se sube al repositorio.

## 3. Levantar el servidor y la app

```bash
cd infra
./mosquitto/crear_usuarios.sh
docker compose --profile app up -d --build
docker compose --profile app ps
```

La primera compilación tarda unos minutos. Después, abre **http://localhost:8080** y entra con `ADMIN_CORREO` y `ADMIN_CONTRASENA`. Cambia la contraseña en **Mi cuenta**.

Para las notificaciones, genera las claves VAPID, agrégalas a `infra/.env` y reinicia el servidor:

```bash
docker compose --profile app exec servidor greensense vapid
docker compose --profile app up -d servidor
```

## 4. Registrar el invernadero y el nodo

En la app, entra a **Configuración**:

1. **Cultivos y umbrales:** revisa los rangos; viene "Hortalizas de hoja" con los de la propuesta.
2. **Invernaderos:** agrega uno, por ejemplo `invernadero1`, y elige su cultivo.
3. **Nodos:** registra el nodo con el mismo identificador que pusiste en `MQTT_NODOS`, por ejemplo `maceta1`.

Si agregas un nodo después, también hay que agregarlo a `MQTT_NODOS`, volver a correr `./mosquitto/crear_usuarios.sh` y reiniciar el broker con `docker compose restart mosquitto`.

## 5. Preparar el nodo

Las conexiones y la calibración del sensor de suelo están en [firmware/README.md](../firmware/README.md).

1. Busca la IP de la computadora en la red: `ip addr` en Linux o `ipconfig` en Windows.
2. Crea la configuración:

   ```bash
   cd firmware
   cp include/config_nodo.example.h include/config_nodo.h
   ```

3. Edita `include/config_nodo.h`: el WiFi, `MQTT_HOST` con la IP de la computadora, `NODO_ID`, su contraseña de `MQTT_NODOS`, el invernadero y los sensores.
4. Conecta el ESP32 por USB y carga el firmware:

   ```bash
   pio run -t upload
   pio device monitor    # opcional: para ver lo que hace. Se sale con Ctrl+C
   ```

5. Calibra el sensor de suelo y vuelve a cargar.
6. Desconéctalo de la computadora, conéctalo a un cargador de celular y entierra el sensor hasta su raya.

En uno o dos minutos, el LED verde debe quedar fijo y el nodo debe aparecer en el panel como **conectado**.

**La IP de la computadora debe mantenerse.** Si cambia de red o el router le da otra IP, el nodo deja de llegar al broker. Lo más seguro es reservarle la IP en el router; si cambia, hay que actualizar `MQTT_HOST` y volver a cargar el firmware.

## 6. Notificaciones en el teléfono

El push necesita HTTPS. Sigue [infra/README.md](../infra/README.md), sección "HTTPS con un túnel". **El túnel publica la app en internet:** antes de usarlo, corre `./revisar_secretos.sh` y cambia las contraseñas de prueba.

## 7. Si algo falla

| Síntoma | Qué revisar |
|---|---|
| `Falta DB_CONTRASENA` al levantar Docker | Falta `infra/.env` (sección 2) |
| La app no abre | `docker compose --profile app ps` y `docker compose --profile app logs servidor` |
| "Reconectando…" permanente en el panel | Que el contenedor `servidor` esté activo. Solo debe correr un servidor a la vez |
| El nodo no aparece y el LED parpadea rápido | No se conecta al WiFi: nombre, contraseña y que sea de 2.4 GHz |
| El LED parpadea lento (1 por segundo) | Tiene WiFi, pero no llega al broker: `MQTT_HOST`, que esté en la misma red, la contraseña en `MQTT_NODOS` y haber corrido `crear_usuarios.sh` |
| Dos destellos cada 2 s | El sensor de aire no responde: revisa los cables |
| El nodo llega al broker, pero no se guardan lecturas | Regístralo en **Configuración > Nodos** con el mismo identificador e invernadero |
| El sustrato marca 0 % | El sensor está al aire o sin calibrar: entiérralo, riega y revisa la calibración |
| `/dev/ttyUSB0` no aparece | El cable solo carga: prueba otro |
| La carga falla con "No serial data received" | Revisa que `upload_speed` siga en 115200 en `platformio.ini` |
| Se perdieron lecturas | El nodo guarda hasta 24 horas: la computadora debe encenderse antes de que pasen |
