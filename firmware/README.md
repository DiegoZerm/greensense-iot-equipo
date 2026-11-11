# Firmware del nodo

Firmware del ESP32 con PlatformIO y el framework Arduino. Sigue el contrato de [`docs/contrato-mqtt.md`](../docs/contrato-mqtt.md).

## Conexiones

| Componente | Pin del ESP32 | Notas |
|---|---|---|
| DHT11 o DHT22, datos | GPIO 4 | VCC a **3V3**, no a 5 V. Si es el sensor suelto de 4 patas, lleva una resistencia de 10 kΩ entre datos y VCC |
| Sensor capacitivo de suelo, salida | GPIO 34 | Opcional. VCC a 3V3. Necesita un pin del ADC1, porque el ADC2 no funciona con el WiFi encendido |
| LED de estado | GPIO 2 | Es el LED integrado del DevKit |
| LED verde (opcional) | GPIO 25 | Pata larga al pin, pata corta a una resistencia de 220 Ω y de ahí a GND. `PIN_LED_VERDE` |
| LED rojo (opcional) | GPIO 26 | Igual que el verde. `PIN_LED_ROJO` |

Todas las tierras (GND) van juntas: la del ESP32, la de los sensores y las de los LEDs.

## Calibración del sensor de suelo

Cada sensor capacitivo da valores distintos, así que hay que medir los dos extremos:

1. Con `SENSOR_SUELO 1`, cargar el firmware y abrir el monitor serie. Cada lectura muestra el valor crudo, por ejemplo `humedad_sustrato=48.2% (adc 2210)`.
2. Con el sensor **al aire y seco**, anotar el `adc` (suele andar entre 2800 y 3300): es `SUELO_ADC_SECO`.
3. Con el sensor **metido en un vaso de agua hasta la raya**, sin mojar la parte de los componentes, anotar el `adc` (suele andar entre 1200 y 1600): es `SUELO_ADC_HUMEDO`.
4. Poner los dos valores en `config_nodo.h` y volver a cargar.

## Configuración y carga

```bash
cd firmware
cp include/config_nodo.example.h include/config_nodo.h   # WiFi, broker, nodo y sensores
pio run -t upload             # compila y carga (a 115200 baudios, la velocidad por defecto falla en algunos adaptadores)
pio device monitor            # salida serie a 115200
pio test -e native            # pruebas en la computadora
```

`config_nodo.h` no se sube al repo porque contiene contraseñas. El usuario MQTT del nodo es `NODO_ID`, y su contraseña debe estar en `MQTT_NODOS` de `infra/.env`.

## Cómo funciona

1. **Muestreo:** cada `PERIODO_S` segundos toma `MUESTRAS` muestras separadas 2.5 s. Descarta las fallidas y las que salen del rango del sensor, y combina las demás con la mediana. Si menos de la mitad son válidas, la variable se publica como `null`.
2. **Cola:** cada lectura entra a una cola de 1440 lugares, 24 horas a 60 s por lectura, para que la computadora del servidor pueda pasar la noche apagada. Si se llena, se descarta la más vieja.
3. **Envío:** con WiFi y broker disponibles, publica la lectura más vieja con QoS 1 usando el cliente MQTT de ESP-IDF, y solo la quita de la cola cuando el broker confirma que la recibió. Si no llega la confirmación, la reenvía; el servidor descarta los duplicados.
4. **Hora:** la hora se obtiene por NTP. Una lectura tomada antes de sincronizar guarda su `millis()`, y su hora se calcula al enviarla.
5. **Identidad:** el contador `arranque` se guarda en la memoria no volátil y aumenta en cada encendido. `seq` empieza en 0 en cada arranque.
6. **Estado:** al conectarse publica su configuración en el tema `estado`, con retención. Si se cae sin avisar, el broker publica `desconectado` como su última voluntad.

## LED de estado

| Patrón | Significado |
|---|---|
| Parpadeo rápido (4 por segundo) | Sin WiFi |
| Parpadeo lento (1 por segundo) | Con WiFi, sin broker |
| Dos destellos cada 2 s | El sensor de aire no responde |
| Un destello breve cada 3 s | Todo bien |

Con LEDs externos, el verde queda encendido fijo mientras todo funciona y el rojo parpadea con el patrón de la falla.

## Código

- `lib/nucleo/`: lógica que no toca hardware (filtro, calibración del suelo, cola, mensajes JSON, hora y LED). Se prueba en la computadora con `pio test -e native`, incluida una prueba que compara el JSON generado con los ejemplos del contrato.
- `src/main.cpp`: sensores, WiFi, NTP y MQTT.
