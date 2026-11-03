// Mensajes del contrato MQTT v1 (docs/contrato-mqtt.md).
#pragma once

#include <cstddef>
#include <cstdint>

#include "lectura.h"

namespace gs {

struct EstadoNodo {
    bool conectado;
    uint32_t arranque;
    const char* firmware;
    SensorAire sensorAire;
    bool sensorSuelo;
    uint16_t periodoS;
};

// Cada función escribe en `destino` y devuelve la longitud, o 0 si no cupo.
size_t formatearHora(int64_t ts, char* destino, size_t capacidad);
size_t armarTema(const char* invernadero, const char* nodo, const char* tipo, char* destino,
                 size_t capacidad);
size_t serializarLectura(const Lectura& lectura, const char* nodo, char* destino,
                         size_t capacidad);
size_t serializarEstado(const EstadoNodo& estado, char* destino, size_t capacidad);

}  // namespace gs
