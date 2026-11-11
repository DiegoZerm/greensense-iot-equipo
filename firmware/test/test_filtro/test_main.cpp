#include <filtro.h>
#include <unity.h>

#include <cmath>
#include <initializer_list>

using gs::Filtro;

void setUp() {}
void tearDown() {}

void test_mediana_de_muestras_impares() {
    Filtro f({0, 50});
    for (float v : {24.0f, 26.0f, 25.0f}) f.agregar(v);
    TEST_ASSERT_EQUAL_FLOAT(25.0f, f.resultado(1));
}

void test_mediana_de_muestras_pares() {
    Filtro f({0, 50});
    for (float v : {24.0f, 25.0f, 26.0f, 30.0f}) f.agregar(v);
    TEST_ASSERT_EQUAL_FLOAT(25.5f, f.resultado(1));
}

void test_un_pico_aislado_no_mueve_el_resultado() {
    Filtro f({0, 50});
    for (float v : {24.0f, 24.1f, 49.0f, 24.2f, 24.1f}) f.agregar(v);
    TEST_ASSERT_EQUAL_FLOAT(24.1f, f.resultado(3));
}

void test_descarta_fallas_y_valores_fuera_de_rango() {
    Filtro f({20, 90});
    for (float v : {NAN, 95.0f, 10.0f, 60.0f, 62.0f}) f.agregar(v);
    TEST_ASSERT_EQUAL_UINT8(5, f.total());
    TEST_ASSERT_EQUAL_UINT8(2, f.validas());
    TEST_ASSERT_EQUAL_FLOAT(61.0f, f.resultado(2));
}

void test_sin_suficientes_validas_es_nan() {
    Filtro f({0, 50});
    for (float v : {NAN, NAN, 25.0f}) f.agregar(v);
    TEST_ASSERT_TRUE(std::isnan(f.resultado(2)));
}

void test_sin_muestras_es_nan() {
    Filtro f({0, 50});
    TEST_ASSERT_TRUE(std::isnan(f.resultado(0)));
}

void test_reiniciar_borra_el_ciclo_anterior() {
    Filtro f({0, 50});
    f.agregar(40.0f);
    f.reiniciar();
    f.agregar(20.0f);
    TEST_ASSERT_EQUAL_FLOAT(20.0f, f.resultado(1));
    TEST_ASSERT_EQUAL_UINT8(1, f.total());
}

void test_limites_del_rango_son_validos() {
    Filtro f(gs::rangos(gs::SensorAire::DHT11).humedad);
    f.agregar(20.0f);
    f.agregar(90.0f);
    TEST_ASSERT_EQUAL_UINT8(2, f.validas());
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_mediana_de_muestras_impares);
    RUN_TEST(test_mediana_de_muestras_pares);
    RUN_TEST(test_un_pico_aislado_no_mueve_el_resultado);
    RUN_TEST(test_descarta_fallas_y_valores_fuera_de_rango);
    RUN_TEST(test_sin_suficientes_validas_es_nan);
    RUN_TEST(test_sin_muestras_es_nan);
    RUN_TEST(test_reiniciar_borra_el_ciclo_anterior);
    RUN_TEST(test_limites_del_rango_son_validos);
    return UNITY_END();
}
