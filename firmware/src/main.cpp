// Nodo GreenSense IoT.
//
// Cada PERIODO_S toma MUESTRAS muestras de los sensores, las combina en una lectura y
// la guarda en una cola. Las lecturas se publican por MQTT con QoS 1 y solo salen de la
// cola cuando el broker confirma que las recibió, así que una caída del WiFi o del
// broker no hace perder datos. El protocolo está en docs/contrato-mqtt.md.
#include <Arduino.h>
#include <DHT.h>
#include <Preferences.h>
#include <WiFi.h>
#include <calibracion.h>
#include <cola.h>
#include <filtro.h>
#include <hora.h>
#include <led.h>
#include <mensaje.h>
#include <mqtt_client.h>

#include <atomic>
#include <ctime>

#if __has_include("config_nodo.h")
#include "config_nodo.h"
#else
#warning "Falta include/config_nodo.h: se usa config_nodo.example.h"
#include "config_nodo.example.h"
#endif

static_assert(SENSOR_AIRE == 11 || SENSOR_AIRE == 22, "SENSOR_AIRE debe ser 11 (DHT11) o 22 (DHT22)");
static_assert(MUESTRAS >= 1 && MUESTRAS <= gs::Filtro::kMaximoMuestras, "MUESTRAS fuera de rango");

// LEDs externos opcionales (verde y rojo). -1 si no están conectados; las
// configuraciones viejas que no los definen siguen compilando.
#ifndef PIN_LED_VERDE
#define PIN_LED_VERDE -1
#endif
#ifndef PIN_LED_ROJO
#define PIN_LED_ROJO -1
#endif

namespace {

constexpr gs::SensorAire kSensorAire = SENSOR_AIRE == 11 ? gs::SensorAire::DHT11 : gs::SensorAire::DHT22;
// El DHT22 necesita al menos 2 s entre lecturas.
constexpr uint32_t kIntervaloMuestraMs = 2500;
static_assert(MUESTRAS * kIntervaloMuestraMs < PERIODO_S * 1000UL, "Las muestras no caben en PERIODO_S");
// Con un periodo de 60 s, 1440 lecturas son 24 horas sin conexión: alcanza para que
// la computadora del servidor pase la noche apagada sin perder datos. No cabe más en la
// RAM estática (unos 58 KB) sin quitarle memoria al WiFi.
constexpr size_t kCapacidadCola = 1440;
constexpr uint8_t kMinimoValidas = (MUESTRAS + 1) / 2;

DHT dht(PIN_DHT, SENSOR_AIRE);
gs::ColaEnvio<kCapacidadCola> cola;

gs::Filtro filtroTemperatura(gs::rangos(kSensorAire).temperatura);
gs::Filtro filtroHumedad(gs::rangos(kSensorAire).humedad);
gs::Filtro filtroSustrato(gs::kRangoSustrato);

uint32_t arranque = 0;
uint32_t seq = 0;
uint32_t proximoCicloMs = 0;
uint32_t proximaMuestraMs = 0;
uint8_t muestrasTomadas = 0;
bool cicloActivo = false;
bool fallaSensor = false;
float ultimoAdcSuelo = NAN;

char temaLecturas[96];
char temaEstado[96];
char mensajeConectado[192];
char mensajeDesconectado[48];
char uriBroker[96];

// El cliente MQTT corre en su propia tarea; se comunica con loop() por estas variables.
esp_mqtt_client_handle_t mqtt = nullptr;
QueueHandle_t confirmaciones = nullptr;  // id de cada publicación que el broker confirmó
std::atomic<bool> brokerConectado{false};
std::atomic<bool> brokerPerdido{false};

void alEventoMqtt(void*, esp_event_base_t, int32_t idEvento, void* datos) {
    auto* evento = static_cast<esp_mqtt_event_handle_t>(datos);
    switch (idEvento) {
        case MQTT_EVENT_CONNECTED:
            esp_mqtt_client_publish(mqtt, temaEstado, mensajeConectado, 0, 1, 1);
            brokerConectado = true;
            break;
        case MQTT_EVENT_DISCONNECTED:
            brokerConectado = false;
            brokerPerdido = true;
            break;
        case MQTT_EVENT_PUBLISHED: {
            const int id = evento->msg_id;
            xQueueSend(confirmaciones, &id, 0);
            break;
        }
        default:
            break;
    }
}

void iniciarMqtt() {
    esp_mqtt_client_config_t config = {};
    config.uri = uriBroker;
    config.client_id = NODO_ID;
    config.username = NODO_ID;
    config.password = MQTT_CONTRASENA;
    // Si el nodo se cae sin avisar, el broker publica este estado por él.
    config.lwt_topic = temaEstado;
    config.lwt_msg = mensajeDesconectado;
    config.lwt_qos = 1;
    config.lwt_retain = 1;
    config.keepalive = 30;
    config.reconnect_timeout_ms = 5000;
    config.buffer_size = 1024;

    mqtt = esp_mqtt_client_init(&config);
    esp_mqtt_client_register_event(mqtt, MQTT_EVENT_ANY, alEventoMqtt, nullptr);
    esp_mqtt_client_start(mqtt);
    Serial.printf("MQTT: conectando a %s como %s\n", uriBroker, NODO_ID);
}

int64_t ahoraEpoch() { return static_cast<int64_t>(time(nullptr)); }

float leerSuelo() {
    // Promedia varias lecturas del ADC para quitar ruido.
    uint32_t suma = 0;
    for (int i = 0; i < 16; i++) {
        suma += analogRead(PIN_SUELO);
    }
    ultimoAdcSuelo = suma / 16.0f;
    return gs::porcentajeSuelo(ultimoAdcSuelo, SUELO_ADC_SECO, SUELO_ADC_HUMEDO);
}

void iniciarCiclo(uint32_t ahora) {
    filtroTemperatura.reiniciar();
    filtroHumedad.reiniciar();
    filtroSustrato.reiniciar();
    muestrasTomadas = 0;
    proximaMuestraMs = ahora;
    cicloActivo = true;
}

void imprimirValor(const char* nombre, float valor, const char* unidad) {
    if (isnan(valor)) {
        Serial.printf(" %s=null", nombre);
    } else {
        Serial.printf(" %s=%.1f%s", nombre, valor, unidad);
    }
}

void terminarCiclo(uint32_t ahora) {
    gs::Lectura lectura;
    lectura.arranque = arranque;
    lectura.seq = seq++;
    lectura.msCaptura = ahora;
    const int64_t epoch = ahoraEpoch();
    lectura.ts = gs::horaValida(epoch) ? epoch : 0;
    lectura.temperatura = filtroTemperatura.resultado(kMinimoValidas);
    lectura.humedad_aire = filtroHumedad.resultado(kMinimoValidas);
    lectura.humedad_sustrato = SENSOR_SUELO ? filtroSustrato.resultado(kMinimoValidas) : NAN;
    lectura.muestras = MUESTRAS;
    lectura.rssi = WiFi.status() == WL_CONNECTED ? static_cast<int8_t>(WiFi.RSSI()) : 0;
    cola.agregar(lectura);

    fallaSensor = isnan(lectura.temperatura) && isnan(lectura.humedad_aire);
    Serial.printf("Lectura %lu:", static_cast<unsigned long>(lectura.seq));
    imprimirValor("temperatura", lectura.temperatura, "C");
    imprimirValor("humedad_aire", lectura.humedad_aire, "%");
    imprimirValor("humedad_sustrato", lectura.humedad_sustrato, "%");
    if (SENSOR_SUELO) {
        // Valor crudo para calibrar: SUELO_ADC_SECO al aire y SUELO_ADC_HUMEDO en agua.
        Serial.printf(" (adc %.0f)", ultimoAdcSuelo);
    }
    Serial.printf(" | validas %u/%u | %s | en cola: %u", filtroTemperatura.validas(), MUESTRAS,
                  lectura.ts ? "con hora" : "sin hora todavia", static_cast<unsigned>(cola.tamano()));
    if (cola.descartadas() > 0) {
        Serial.printf(" | descartadas: %lu", static_cast<unsigned long>(cola.descartadas()));
    }
    Serial.println();
    cicloActivo = false;
}

void atenderMuestreo(uint32_t ahora) {
    if (!cicloActivo && static_cast<int32_t>(ahora - proximoCicloMs) >= 0) {
        proximoCicloMs += PERIODO_S * 1000UL;
        // Si el nodo se atrasó (por ejemplo, durante una conexión lenta), no acumula ciclos.
        if (static_cast<int32_t>(ahora - proximoCicloMs) >= 0) {
            proximoCicloMs = ahora + PERIODO_S * 1000UL;
        }
        iniciarCiclo(ahora);
    }
    if (!cicloActivo || static_cast<int32_t>(ahora - proximaMuestraMs) < 0) {
        return;
    }
    // La biblioteca DHT guarda la lectura 2 s, así que ambas llamadas usan la misma medición.
    filtroTemperatura.agregar(dht.readTemperature());
    filtroHumedad.agregar(dht.readHumidity());
    if (SENSOR_SUELO) {
        filtroSustrato.agregar(leerSuelo());
    }
    muestrasTomadas++;
    proximaMuestraMs += kIntervaloMuestraMs;
    if (muestrasTomadas == MUESTRAS) {
        terminarCiclo(ahora);
    }
}

void atenderRed() {
    if (mqtt == nullptr && WiFi.status() == WL_CONNECTED) {
        Serial.printf("WiFi: conectado a %s, IP %s\n", WIFI_SSID, WiFi.localIP().toString().c_str());
        iniciarMqtt();
    }
    if (brokerPerdido.exchange(false)) {
        Serial.println("MQTT: conexión perdida, se reintenta");
        cola.conexionPerdida();
    }
    int id;
    while (xQueueReceive(confirmaciones, &id, 0) == pdTRUE) {
        cola.confirmar(id);
    }
}

void atenderEnvio(uint32_t ahora) {
    const gs::Lectura* pendiente = cola.siguiente(brokerConectado, ahora);
    if (pendiente == nullptr) {
        return;
    }
    gs::Lectura lectura = *pendiente;
    if (!gs::completarHora(lectura, ahoraEpoch(), ahora)) {
        return;  // espera a que NTP dé la hora
    }
    char json[320];
    if (gs::serializarLectura(lectura, NODO_ID, json, sizeof json) == 0) {
        Serial.println("Error: la lectura no cupo en el mensaje");
        return;
    }
    const int id = esp_mqtt_client_publish(mqtt, temaLecturas, json, 0, 1, 0);
    if (id > 0) {
        cola.marcarEnviada(id, ahora);
    }
}

void actualizarLed(uint32_t ahora) {
    gs::EstadoLed estado = gs::EstadoLed::Operando;
    if (WiFi.status() != WL_CONNECTED) {
        estado = gs::EstadoLed::SinWifi;
    } else if (!brokerConectado) {
        estado = gs::EstadoLed::SinBroker;
    } else if (fallaSensor) {
        estado = gs::EstadoLed::FallaSensor;
    }
    digitalWrite(PIN_LED, gs::ledEncendido(estado, ahora) ? HIGH : LOW);
    const gs::LedsExternos externos = gs::ledsExternos(estado, ahora);
    if (PIN_LED_VERDE >= 0) {
        digitalWrite(PIN_LED_VERDE, externos.verde ? HIGH : LOW);
    }
    if (PIN_LED_ROJO >= 0) {
        digitalWrite(PIN_LED_ROJO, externos.rojo ? HIGH : LOW);
    }
}

}  // namespace

void setup() {
    Serial.begin(115200);
    pinMode(PIN_LED, OUTPUT);
    if (PIN_LED_VERDE >= 0) {
        pinMode(PIN_LED_VERDE, OUTPUT);
    }
    if (PIN_LED_ROJO >= 0) {
        pinMode(PIN_LED_ROJO, OUTPUT);
    }

    // El contador de arranques vive en la memoria no volátil para que (arranque, seq)
    // identifique cada lectura aunque el nodo se reinicie.
    Preferences preferencias;
    preferencias.begin("greensense", false);
    arranque = preferencias.getUInt("arranque", 0) + 1;
    preferencias.putUInt("arranque", arranque);
    preferencias.end();

    dht.begin();
    if (SENSOR_SUELO) {
        analogSetPinAttenuation(PIN_SUELO, ADC_11db);
    }

    gs::armarTema(INVERNADERO_ID, NODO_ID, "lecturas", temaLecturas, sizeof temaLecturas);
    gs::armarTema(INVERNADERO_ID, NODO_ID, "estado", temaEstado, sizeof temaEstado);
    gs::EstadoNodo estado{true, arranque, FIRMWARE_VERSION, kSensorAire, SENSOR_SUELO != 0, PERIODO_S};
    gs::serializarEstado(estado, mensajeConectado, sizeof mensajeConectado);
    estado.conectado = false;
    gs::serializarEstado(estado, mensajeDesconectado, sizeof mensajeDesconectado);
    snprintf(uriBroker, sizeof uriBroker, "mqtt://%s:%d", MQTT_HOST, MQTT_PUERTO);
    confirmaciones = xQueueCreate(16, sizeof(int));

    Serial.printf("\nGreenSense %s/%s, firmware %s, arranque %lu\n", INVERNADERO_ID, NODO_ID,
                  FIRMWARE_VERSION, static_cast<unsigned long>(arranque));
    Serial.printf("Sensor de aire: %s en el pin %d. Sensor de suelo: %s\n", gs::nombre(kSensorAire),
                  PIN_DHT, SENSOR_SUELO ? "conectado" : "no conectado");
    Serial.printf("Cola de %u lecturas. Memoria libre: %u bytes\n",
                  static_cast<unsigned>(kCapacidadCola), static_cast<unsigned>(ESP.getFreeHeap()));

    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_CONTRASENA);
    configTime(0, 0, "pool.ntp.org", "time.google.com");

    // Primera lectura a los 2 s, para dar tiempo al sensor de estabilizarse.
    proximoCicloMs = millis() + 2000;
}

void loop() {
    const uint32_t ahora = millis();
    atenderRed();
    atenderMuestreo(ahora);
    atenderEnvio(ahora);
    actualizarLed(ahora);
    delay(10);
}
