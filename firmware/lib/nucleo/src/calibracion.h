#pragma once

namespace gs {

// Convierte la lectura del ADC del sensor capacitivo a porcentaje de humedad.
// El sensor da un valor más alto mientras más seco está: `adcSeco` es la lectura al
// aire y `adcHumedo` sumergido en agua. Fuera de ese intervalo, con un margen del 10 %,
// se considera que el sensor está desconectado o dañado y se devuelve NAN.
float porcentajeSuelo(float adc, int adcSeco, int adcHumedo);

}  // namespace gs
