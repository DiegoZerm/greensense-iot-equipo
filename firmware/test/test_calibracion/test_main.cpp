#include <calibracion.h>
#include <unity.h>

#include <cmath>

using gs::porcentajeSuelo;

constexpr int kSeco = 3000;
constexpr int kHumedo = 1300;

void setUp() {}
void tearDown() {}

void test_extremos_de_la_calibracion() {
    TEST_ASSERT_EQUAL_FLOAT(0.0f, porcentajeSuelo(kSeco, kSeco, kHumedo));
    TEST_ASSERT_EQUAL_FLOAT(100.0f, porcentajeSuelo(kHumedo, kSeco, kHumedo));
}

void test_punto_medio() {
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 50.0f, porcentajeSuelo(2150, kSeco, kHumedo));
}

void test_poco_fuera_del_tramo_se_limita() {
    TEST_ASSERT_EQUAL_FLOAT(0.0f, porcentajeSuelo(3100, kSeco, kHumedo));
    TEST_ASSERT_EQUAL_FLOAT(100.0f, porcentajeSuelo(1200, kSeco, kHumedo));
}

void test_sensor_desconectado_es_nan() {
    TEST_ASSERT_TRUE(std::isnan(porcentajeSuelo(4095, kSeco, kHumedo)));
    TEST_ASSERT_TRUE(std::isnan(porcentajeSuelo(0, kSeco, kHumedo)));
}

void test_calibracion_invertida_es_nan() {
    TEST_ASSERT_TRUE(std::isnan(porcentajeSuelo(2000, kHumedo, kSeco)));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_extremos_de_la_calibracion);
    RUN_TEST(test_punto_medio);
    RUN_TEST(test_poco_fuera_del_tramo_se_limita);
    RUN_TEST(test_sensor_desconectado_es_nan);
    RUN_TEST(test_calibracion_invertida_es_nan);
    return UNITY_END();
}
