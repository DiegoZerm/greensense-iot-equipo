// Tipos compartidos del nodo. No dependen de Arduino, así que se prueban en la computadora.
#pragma once

#include <cmath>
#include <cstdint>

namespace gs {

enum class SensorAire : uint8_t { DHT11, DHT22 };

struct Rango {
    float minimo;
    float maximo;
};

struct RangosSensor {
    Rango temperatura;
    Rango humedad;
};

// Rango que cada sensor puede medir según su hoja de datos (igual que en el servidor).
constexpr RangosSensor rangos(SensorAire sensor) {
    return sensor == SensorAire::DHT11 ? RangosSensor{{0.0f, 50.0f}, {20.0f, 90.0f}}
                                       : RangosSensor{{-40.0f, 80.0f}, {0.0f, 100.0f}};
}

constexpr Rango kRangoSustrato{0.0f, 100.0f};

const char* nombre(SensorAire sensor);

// NAN representa un valor que no existe (sin sensor o lectura fallida) y se publica como null.
struct Lectura {
    uint32_t arranque = 0;
    uint32_t seq = 0;
    int64_t ts = 0;       // segundos desde 1970 en UTC; 0 si aún no hay hora por NTP
    uint32_t msCaptura = 0;  // millis() al tomar la lectura, para calcular ts después
    float temperatura = NAN;
    float humedad_aire = NAN;
    float humedad_sustrato = NAN;
    uint8_t muestras = 0;
    int8_t rssi = 0;  // 0: desconocido, no se publica
};

}  // namespace gs
