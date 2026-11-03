#include "lectura.h"

namespace gs {

const char* nombre(SensorAire sensor) {
    return sensor == SensorAire::DHT11 ? "DHT11" : "DHT22";
}

}  // namespace gs
