// Configuración del nodo. Copiar a include/config_nodo.h y llenar con los datos reales.
// config_nodo.h no se sube al repo porque contiene contraseñas.
#pragma once

// Red WiFi
#define WIFI_SSID "mi-red"
#define WIFI_CONTRASENA "contrasena-wifi"

// Broker MQTT (IP de la computadora donde corre docker compose)
#define MQTT_HOST "192.168.1.10"
#define MQTT_PUERTO 1883

// Identidad: el usuario MQTT del nodo es NODO_ID (ver infra/.env, MQTT_NODOS)
#define INVERNADERO_ID "invernadero1"
#define NODO_ID "nodo1"
#define MQTT_CONTRASENA "contrasena-del-nodo"

// Sensor de temperatura y humedad del aire: 11 para DHT11, 22 para DHT22
#define SENSOR_AIRE 22
#define PIN_DHT 4

// Sensor capacitivo de humedad del sustrato: 0 si no está conectado
#define SENSOR_SUELO 1
#define PIN_SUELO 34
// Lecturas del ADC para calibrar: sensor al aire (seco) y sumergido en agua (húmedo)
#define SUELO_ADC_SECO 3000
#define SUELO_ADC_HUMEDO 1300

// LED de estado (el LED integrado del DevKit está en el pin 2)
#define PIN_LED 2
// LEDs externos, cada uno con su resistencia de 220 Ω a GND. -1 si no se usan.
// Verde fijo: todo bien. Rojo: parpadea con el patrón de la falla.
#define PIN_LED_VERDE 25
#define PIN_LED_ROJO 26

// Muestreo
#define PERIODO_S 60
#define MUESTRAS 5
