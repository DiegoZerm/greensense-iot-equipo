#include <ArduinoJson.h>
#include <mensaje.h>
#include <unity.h>

#include <fstream>
#include <set>
#include <sstream>
#include <string>

using namespace gs;

// Ejemplos del contrato, relativos a la carpeta firmware/ desde donde corren las pruebas.
const char* kEjemplos = "../docs/contrato/ejemplos/";

void setUp() {}
void tearDown() {}

JsonDocument leerEjemplo(const std::string& nombre) {
    std::ifstream archivo(kEjemplos + nombre);
    TEST_ASSERT_TRUE_MESSAGE(archivo.good(), "no se encontró el ejemplo del contrato");
    std::stringstream contenido;
    contenido << archivo.rdbuf();
    JsonDocument doc;
    TEST_ASSERT_FALSE(deserializeJson(doc, contenido.str()));
    return doc;
}

JsonDocument parsear(const char* json) {
    JsonDocument doc;
    TEST_ASSERT_FALSE(deserializeJson(doc, json));
    return doc;
}

std::set<std::string> claves(JsonObjectConst objeto) {
    std::set<std::string> resultado;
    for (JsonPairConst par : objeto) resultado.insert(par.key().c_str());
    return resultado;
}

Lectura lecturaCompleta() {
    Lectura l;
    l.arranque = 12;
    l.seq = 1234;
    l.ts = 1793548800;  // 2026-11-01T16:00:00Z
    l.temperatura = 24.3f;
    l.humedad_aire = 68.1f;
    l.humedad_sustrato = 52.0f;
    l.muestras = 5;
    l.rssi = -61;
    return l;
}

void test_lectura_es_igual_al_ejemplo_del_contrato() {
    char json[320];
    TEST_ASSERT_GREATER_THAN(0, serializarLectura(lecturaCompleta(), "nodo1", json, sizeof json));

    JsonDocument generado = parsear(json);
    JsonDocument ejemplo = leerEjemplo("lectura_completa.json");
    TEST_ASSERT_TRUE(claves(generado.as<JsonObjectConst>()) == claves(ejemplo.as<JsonObjectConst>()));
    for (const char* clave : {"v", "nodo", "arranque", "seq", "ts", "muestras", "rssi"}) {
        TEST_ASSERT_TRUE_MESSAGE(generado[clave] == ejemplo[clave], clave);
    }
    for (const char* clave : {"temperatura", "humedad_aire", "humedad_sustrato"}) {
        TEST_ASSERT_EQUAL_DOUBLE(ejemplo[clave].as<double>(), generado[clave].as<double>());
    }
}

void test_valores_redondeados_a_un_decimal() {
    Lectura l = lecturaCompleta();
    l.temperatura = 24.299999f;
    char json[320];
    serializarLectura(l, "nodo1", json, sizeof json);
    TEST_ASSERT_NOT_NULL(strstr(json, "\"temperatura\":24.3,"));
}

void test_sin_sensor_de_suelo_publica_null() {
    Lectura l = lecturaCompleta();
    l.humedad_sustrato = NAN;
    char json[320];
    serializarLectura(l, "nodo1", json, sizeof json);

    JsonDocument doc = parsear(json);
    TEST_ASSERT_TRUE(doc["humedad_sustrato"].isNull());
    TEST_ASSERT_TRUE(doc.as<JsonObjectConst>()["humedad_sustrato"].is<JsonVariantConst>());
}

void test_rssi_desconocido_no_se_publica() {
    Lectura l = lecturaCompleta();
    l.rssi = 0;
    char json[320];
    serializarLectura(l, "nodo1", json, sizeof json);
    TEST_ASSERT_NULL(strstr(json, "rssi"));
}

void test_buffer_pequeno_devuelve_cero() {
    char json[40];
    TEST_ASSERT_EQUAL(0, serializarLectura(lecturaCompleta(), "nodo1", json, sizeof json));
}

void test_estado_conectado_igual_al_ejemplo() {
    char json[200];
    EstadoNodo estado{true, 3, "0.1.0", SensorAire::DHT11, false, 60};
    TEST_ASSERT_GREATER_THAN(0, serializarEstado(estado, json, sizeof json));
    TEST_ASSERT_TRUE(parsear(json) == leerEjemplo("estado_conectado.json"));
}

void test_estado_desconectado_igual_al_ejemplo() {
    char json[64];
    EstadoNodo estado{false, 3, "0.1.0", SensorAire::DHT11, false, 60};
    serializarEstado(estado, json, sizeof json);
    TEST_ASSERT_TRUE(parsear(json) == leerEjemplo("estado_desconectado.json"));
}

void test_hora_en_utc() {
    char hora[24];
    formatearHora(0, hora, sizeof hora);
    TEST_ASSERT_EQUAL_STRING("1970-01-01T00:00:00Z", hora);
    formatearHora(1793548800, hora, sizeof hora);
    TEST_ASSERT_EQUAL_STRING("2026-11-01T16:00:00Z", hora);
}

void test_tema() {
    char tema[64];
    armarTema("invernadero1", "nodo1", "lecturas", tema, sizeof tema);
    TEST_ASSERT_EQUAL_STRING("greensense/invernadero1/nodo1/lecturas", tema);
    TEST_ASSERT_EQUAL(0, armarTema("invernadero1", "nodo1", "lecturas", tema, 10));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_lectura_es_igual_al_ejemplo_del_contrato);
    RUN_TEST(test_valores_redondeados_a_un_decimal);
    RUN_TEST(test_sin_sensor_de_suelo_publica_null);
    RUN_TEST(test_rssi_desconocido_no_se_publica);
    RUN_TEST(test_buffer_pequeno_devuelve_cero);
    RUN_TEST(test_estado_conectado_igual_al_ejemplo);
    RUN_TEST(test_estado_desconectado_igual_al_ejemplo);
    RUN_TEST(test_hora_en_utc);
    RUN_TEST(test_tema);
    return UNITY_END();
}
