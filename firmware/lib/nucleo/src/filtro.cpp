#include "filtro.h"

#include <algorithm>
#include <cmath>

namespace gs {

void Filtro::agregar(float valor) {
    if (total_ < kMaximoMuestras) {
        total_++;
    }
    if (std::isnan(valor) || valor < rango_.minimo || valor > rango_.maximo) {
        return;
    }
    if (validas_ < kMaximoMuestras) {
        valores_[validas_++] = valor;
    }
}

void Filtro::reiniciar() {
    validas_ = 0;
    total_ = 0;
}

float Filtro::resultado(uint8_t minimoValidas) const {
    if (validas_ == 0 || validas_ < minimoValidas) {
        return NAN;
    }
    float ordenados[kMaximoMuestras];
    std::copy(valores_, valores_ + validas_, ordenados);
    std::sort(ordenados, ordenados + validas_);
    const uint8_t medio = validas_ / 2;
    return validas_ % 2 == 1 ? ordenados[medio] : (ordenados[medio - 1] + ordenados[medio]) / 2.0f;
}

}  // namespace gs
