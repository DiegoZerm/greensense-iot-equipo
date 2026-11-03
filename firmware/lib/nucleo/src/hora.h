#pragma once

#include <cstdint>

#include "lectura.h"

namespace gs {

// Antes de sincronizar por NTP, el reloj del ESP32 empieza en 1970.
constexpr int64_t kHoraMinimaValida = 1735689600;  // 2025-01-01T00:00:00Z

inline bool horaValida(int64_t epoch) { return epoch >= kHoraMinimaValida; }

// Si la lectura se tomó antes de tener hora, la calcula con lo que ha pasado desde
// entonces según millis(). Devuelve false si todavía no se puede saber.
inline bool completarHora(Lectura& lectura, int64_t epochAhora, uint32_t msAhora) {
    if (lectura.ts != 0) {
        return true;
    }
    if (!horaValida(epochAhora)) {
        return false;
    }
    const uint32_t transcurridoMs = msAhora - lectura.msCaptura;  // correcto aunque millis se desborde
    lectura.ts = epochAhora - static_cast<int64_t>(transcurridoMs / 1000);
    return true;
}

}  // namespace gs
