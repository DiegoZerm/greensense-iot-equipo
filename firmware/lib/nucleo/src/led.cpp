#include "led.h"

namespace gs {

bool ledEncendido(EstadoLed estado, uint32_t ms) {
    switch (estado) {
        case EstadoLed::SinWifi:
            return ms % 250 < 125;
        case EstadoLed::SinBroker:
            return ms % 1000 < 500;
        case EstadoLed::FallaSensor: {
            const uint32_t fase = ms % 2000;
            return fase < 100 || (fase >= 250 && fase < 350);
        }
        case EstadoLed::Operando:
            return ms % 3000 < 60;
    }
    return false;
}

LedsExternos ledsExternos(EstadoLed estado, uint32_t ms) {
    if (estado == EstadoLed::Operando) {
        return {true, false};
    }
    return {false, ledEncendido(estado, ms)};
}

}  // namespace gs
