#include "calibracion.h"

#include <algorithm>
#include <cmath>

namespace gs {

float porcentajeSuelo(float adc, int adcSeco, int adcHumedo) {
    const float tramo = static_cast<float>(adcSeco - adcHumedo);
    if (std::isnan(adc) || tramo <= 0) {
        return NAN;
    }
    const float margen = tramo * 0.10f;
    if (adc > adcSeco + margen || adc < adcHumedo - margen) {
        return NAN;
    }
    const float porcentaje = (adcSeco - adc) / tramo * 100.0f;
    return std::clamp(porcentaje, 0.0f, 100.0f);
}

}  // namespace gs
