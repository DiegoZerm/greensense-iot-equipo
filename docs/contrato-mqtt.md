# Contrato MQTT

Define los mensajes que intercambian los nodos y el servidor. El firmware y el servidor dependen de este documento, así que cualquier cambio incompatible exige subir el campo `v`.

Los esquemas JSON están en [`contrato/`](contrato), y los ejemplos de [`contrato/ejemplos/`](contrato/ejemplos) se usan en las pruebas del servidor.

## Temas

| Tema | Publica | QoS | Retenido | Contenido |
|---|---|---|---|---|
| `greensense/{invernadero}/{nodo}/lecturas` | nodo | 1 | no | [lectura](contrato/lectura.schema.json) |
| `greensense/{invernadero}/{nodo}/estado` | nodo | 1 | sí | [estado](contrato/estado.schema.json) |
| `greensense/{invernadero}/{nodo}/comandos` | servidor | 1 | no | reservado para la etapa de actuadores |

- `{invernadero}` y `{nodo}` son identificadores en minúsculas, con dígitos y guiones (`^[a-z0-9-]{1,32}$`).
- El servidor se suscribe a `greensense/+/+/lecturas` y `greensense/+/+/estado`.

## Lectura

```json
{
  "v": 1,
  "nodo": "nodo1",
  "arranque": 12,
  "seq": 1234,
  "ts": "2026-11-01T16:00:00Z",
  "temperatura": 24.3,
  "humedad_aire": 68.1,
  "humedad_sustrato": 52.0,
  "muestras": 5,
  "rssi": -61
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `v` | entero | versión del contrato, hoy `1` |
| `nodo` | texto | debe coincidir con el `{nodo}` del tema |
| `arranque` | entero | contador de encendidos, guardado en la memoria del nodo |
| `seq` | entero | consecutivo de lecturas dentro del arranque; vuelve a 0 al encender |
| `ts` | fecha y hora ISO 8601 en UTC | momento de la lectura, por NTP |
| `temperatura` | número o `null` | °C |
| `humedad_aire` | número o `null` | % HR |
| `humedad_sustrato` | número o `null` | %, ya calibrado en el nodo |
| `muestras` | entero, opcional | muestras promediadas para esta lectura |
| `rssi` | entero, opcional | señal WiFi en dBm |

Reglas:

- **Una variable es `null`** cuando el nodo no tiene ese sensor (por ejemplo, sin sensor de suelo) o cuando la lectura falló o salió del rango físico del sensor. El nodo nunca inventa valores. El servidor guarda el `null` y no evalúa las reglas de esa variable.
- **Identidad de una lectura:** `(nodo, arranque, seq)`. El servidor descarta los duplicados, que aparecen cuando el nodo reenvía lecturas guardadas sin conexión.
- **Lecturas perdidas:** dentro de un mismo `arranque`, un salto en `seq` indica lecturas que no llegaron.
- **Hora:** el nodo no publica hasta sincronizar por NTP. Las lecturas reenviadas conservan su `ts` original.

## Estado

Al conectarse, el nodo publica un estado retenido con su configuración. Además registra como mensaje de última voluntad el de desconexión, que el broker publica si el nodo se cae sin despedirse.

```json
{"v": 1, "estado": "conectado", "arranque": 3, "firmware": "0.1.0", "sensor_aire": "DHT11", "sensor_suelo": false, "periodo_s": 60}
```

```json
{"v": 1, "estado": "desconectado"}
```

Con `sensor_aire`, el servidor sabe qué rango físico puede medir el nodo:

| Sensor | Temperatura | Humedad relativa |
|---|---|---|
| DHT11 | 0 a 50 °C | 20 a 90 % |
| DHT22 | −40 a 80 °C | 0 a 100 % |

El mensaje de última voluntad solo avisa de una caída de la conexión. La desconexión que genera una alerta la detecta el servidor cuando pasa el tiempo definido sin lecturas, porque un nodo puede seguir conectado y aun así no mandar datos.

## Seguridad

- Mosquitto no acepta conexiones anónimas. Cada nodo usa su identificador como usuario MQTT, con su propia contraseña.
- La ACL ([`infra/mosquitto/acl`](../infra/mosquitto/acl)) solo permite que un nodo publique en `greensense/+/<su usuario>/lecturas` y `/estado`, y que lea sus `comandos`.
- El servidor además verifica que el `nodo` del mensaje coincida con el del tema y que el nodo esté registrado en ese invernadero.
