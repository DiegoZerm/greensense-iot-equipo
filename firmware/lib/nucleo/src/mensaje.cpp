#include "mensaje.h"

#include <ArduinoJson.h>

#include <cmath>
#include <cstdio>
#include <ctime>

namespace gs {

namespace {

// Redondea a la precisión de los sensores para no publicar 24.299999.
void asignarValor(JsonDocument& doc, const char* clave, float valor, float factor) {
    if (std::isnan(valor)) {
        doc[clave] = nullptr;
    } else {
        doc[clave] = std::round(static_cast<double>(valor) * factor) / factor;
    }
}

size_t escribir(const JsonDocument& doc, char* destino, size_t capacidad) {
    const size_t necesario = measureJson(doc);
    if (necesario + 1 > capacidad) {
        return 0;
    }
    return serializeJson(doc, destino, capacidad);
}

}  // namespace

size_t formatearHora(int64_t ts, char* destino, size_t capacidad) {
    const time_t segundos = static_cast<time_t>(ts);
    struct tm utc;
    gmtime_r(&segundos, &utc);
    const size_t escritos = strftime(destino, capacidad, "%Y-%m-%dT%H:%M:%SZ", &utc);
    return escritos;
}

size_t armarTema(const char* invernadero, const char* nodo, const char* tipo, char* destino,
                 size_t capacidad) {
    const int escritos =
        snprintf(destino, capacidad, "greensense/%s/%s/%s", invernadero, nodo, tipo);
    return escritos > 0 && static_cast<size_t>(escritos) < capacidad ? escritos : 0;
}

size_t serializarLectura(const Lectura& lectura, const char* nodo, char* destino,
                         size_t capacidad) {
    char hora[24];
    if (formatearHora(lectura.ts, hora, sizeof hora) == 0) {
        return 0;
    }
    JsonDocument doc;
    doc["v"] = 1;
    doc["nodo"] = nodo;
    doc["arranque"] = lectura.arranque;
    doc["seq"] = lectura.seq;
    doc["ts"] = hora;
    asignarValor(doc, "temperatura", lectura.temperatura, 10.0f);
    asignarValor(doc, "humedad_aire", lectura.humedad_aire, 10.0f);
    asignarValor(doc, "humedad_sustrato", lectura.humedad_sustrato, 10.0f);
    if (lectura.muestras > 0) {
        doc["muestras"] = lectura.muestras;
    }
    if (lectura.rssi < 0) {
        doc["rssi"] = lectura.rssi;
    }
    return escribir(doc, destino, capacidad);
}

size_t serializarEstado(const EstadoNodo& estado, char* destino, size_t capacidad) {
    JsonDocument doc;
    doc["v"] = 1;
    if (!estado.conectado) {
        doc["estado"] = "desconectado";
        return escribir(doc, destino, capacidad);
    }
    doc["estado"] = "conectado";
    doc["arranque"] = estado.arranque;
    doc["firmware"] = estado.firmware;
    doc["sensor_aire"] = nombre(estado.sensorAire);
    doc["sensor_suelo"] = estado.sensorSuelo;
    doc["periodo_s"] = estado.periodoS;
    return escribir(doc, destino, capacidad);
}

}  // namespace gs
