#pragma once

#include <cstdint>

namespace gs {

enum class EstadoLed : uint8_t {
    SinWifi,      // parpadeo rápido
    SinBroker,    // parpadeo lento
    FallaSensor,  // dos destellos cada 2 s
    Operando,     // un destello breve cada 3 s
};

// Si el LED debe estar encendido en el instante `ms` para mostrar el estado.
bool ledEncendido(EstadoLed estado, uint32_t ms);

// LEDs externos opcionales: el verde queda fijo mientras todo funciona y el rojo
// repite el patrón de la falla (rápido sin WiFi, lento sin broker, dos destellos si
// falla el sensor). Así se lee el estado de lejos sin contar destellos del integrado.
struct LedsExternos {
    bool verde;
    bool rojo;
};

LedsExternos ledsExternos(EstadoLed estado, uint32_t ms);

}  // namespace gs
