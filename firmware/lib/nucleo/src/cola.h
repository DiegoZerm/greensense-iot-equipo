#pragma once

#include <cstddef>
#include <cstdint>

#include "lectura.h"

namespace gs {

// Cola circular de lecturas pendientes de enviar.
//
// Se envía una lectura a la vez y solo se quita de la cola cuando el broker confirma
// que la recibió (PUBACK de QoS 1). Si la conexión se pierde o la confirmación no llega
// a tiempo, la misma lectura se vuelve a enviar; el servidor descarta el duplicado.
// Si la cola se llena, se descarta la lectura más vieja.
template <size_t N>
class ColaEnvio {
   public:
    static constexpr uint32_t kEsperaConfirmacionMs = 15000;

    void agregar(const Lectura& lectura) {
        if (tamano_ == N) {
            quitarFrente();
            descartadas_++;
        }
        datos_[(inicio_ + tamano_) % N] = lectura;
        tamano_++;
    }

    // La lectura que toca enviar, o nullptr si no hay o si se espera una confirmación.
    const Lectura* siguiente(bool conectado, uint32_t ahoraMs) const {
        if (!conectado || tamano_ == 0) {
            return nullptr;
        }
        if (idEnVuelo_ >= 0 && ahoraMs - enviadaEnMs_ < kEsperaConfirmacionMs) {
            return nullptr;
        }
        return &datos_[inicio_];
    }

    void marcarEnviada(int idMensaje, uint32_t ahoraMs) {
        idEnVuelo_ = idMensaje;
        enviadaEnMs_ = ahoraMs;
    }

    // Devuelve true si la confirmación corresponde a la lectura en vuelo.
    bool confirmar(int idMensaje) {
        if (idEnVuelo_ < 0 || idMensaje != idEnVuelo_ || tamano_ == 0) {
            return false;
        }
        quitarFrente();
        return true;
    }

    void conexionPerdida() { idEnVuelo_ = -1; }

    size_t tamano() const { return tamano_; }
    uint32_t descartadas() const { return descartadas_; }
    bool esperandoConfirmacion() const { return idEnVuelo_ >= 0; }

   private:
    void quitarFrente() {
        inicio_ = (inicio_ + 1) % N;
        tamano_--;
        // La confirmación pendiente era de la lectura que se acaba de quitar.
        idEnVuelo_ = -1;
    }

    Lectura datos_[N];
    size_t inicio_ = 0;
    size_t tamano_ = 0;
    uint32_t descartadas_ = 0;
    int idEnVuelo_ = -1;
    uint32_t enviadaEnMs_ = 0;
};

}  // namespace gs
