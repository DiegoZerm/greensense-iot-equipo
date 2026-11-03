#include <initializer_list>
#include <led.h>
#include <unity.h>

using gs::EstadoLed;
using gs::ledEncendido;

void setUp() {}
void tearDown() {}

// Fracción del tiempo que el LED pasa encendido en `periodo` ms.
float ciclo(EstadoLed estado, uint32_t periodo) {
    uint32_t encendido = 0;
    for (uint32_t ms = 0; ms < periodo; ms++) encendido += ledEncendido(estado, ms);
    return static_cast<float>(encendido) / periodo;
}

// Cuántas veces se enciende en `periodo` ms.
int destellos(EstadoLed estado, uint32_t periodo) {
    int cuenta = 0;
    bool antes = false;
    for (uint32_t ms = 0; ms < periodo; ms++) {
        bool ahora = ledEncendido(estado, ms);
        cuenta += ahora && !antes;
        antes = ahora;
    }
    return cuenta;
}

void test_sin_wifi_parpadea_rapido() {
    TEST_ASSERT_EQUAL(4, destellos(EstadoLed::SinWifi, 1000));
}

void test_sin_broker_parpadea_lento() {
    TEST_ASSERT_EQUAL(1, destellos(EstadoLed::SinBroker, 1000));
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.5f, ciclo(EstadoLed::SinBroker, 1000));
}

void test_falla_de_sensor_da_dos_destellos() {
    TEST_ASSERT_EQUAL(2, destellos(EstadoLed::FallaSensor, 2000));
}

void test_operando_casi_siempre_apagado() {
    TEST_ASSERT_EQUAL(1, destellos(EstadoLed::Operando, 3000));
    TEST_ASSERT_LESS_THAN_FLOAT(0.05f, ciclo(EstadoLed::Operando, 3000));
}

void test_externos_verde_fijo_cuando_todo_funciona() {
    for (uint32_t ms = 0; ms < 3000; ms += 7) {
        const auto leds = gs::ledsExternos(EstadoLed::Operando, ms);
        TEST_ASSERT_TRUE(leds.verde);
        TEST_ASSERT_FALSE(leds.rojo);
    }
}

void test_externos_rojo_con_el_patron_de_la_falla() {
    for (auto estado : {EstadoLed::SinWifi, EstadoLed::SinBroker, EstadoLed::FallaSensor}) {
        for (uint32_t ms = 0; ms < 2000; ms += 7) {
            const auto leds = gs::ledsExternos(estado, ms);
            TEST_ASSERT_FALSE(leds.verde);
            TEST_ASSERT_EQUAL(ledEncendido(estado, ms), leds.rojo);
        }
    }
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_sin_wifi_parpadea_rapido);
    RUN_TEST(test_sin_broker_parpadea_lento);
    RUN_TEST(test_falla_de_sensor_da_dos_destellos);
    RUN_TEST(test_operando_casi_siempre_apagado);
    RUN_TEST(test_externos_verde_fijo_cuando_todo_funciona);
    RUN_TEST(test_externos_rojo_con_el_patron_de_la_falla);
    return UNITY_END();
}
