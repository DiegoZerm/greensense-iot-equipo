#pragma once

#include <cstdint>

#include "lectura.h"

namespace gs {

// Junta las muestras de un ciclo y entrega un solo valor.
// Descarta las muestras fallidas (NAN) y las que salen del rango del sensor, y combina
// las válidas con la mediana, que no se deja arrastrar por un pico aislado.
class Filtro {
   public:
    static constexpr uint8_t kMaximoMuestras = 20;

    explicit Filtro(Rango rango) : rango_(rango) {}

    void agregar(float valor);
    void reiniciar();
    // NAN si hay menos de `minimoValidas` muestras válidas.
    float resultado(uint8_t minimoValidas) const;
    uint8_t validas() const { return validas_; }
    uint8_t total() const { return total_; }

   private:
    Rango rango_;
    float valores_[kMaximoMuestras] = {};
    uint8_t validas_ = 0;
    uint8_t total_ = 0;
};

}  // namespace gs
