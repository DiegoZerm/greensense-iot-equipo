#include <cola.h>
#include <unity.h>

using gs::ColaEnvio;
using gs::Lectura;

void setUp() {}
void tearDown() {}

Lectura lectura(uint32_t seq) {
    Lectura l;
    l.seq = seq;
    return l;
}

void test_sin_conexion_no_entrega_nada() {
    ColaEnvio<4> cola;
    cola.agregar(lectura(0));
    TEST_ASSERT_NULL(cola.siguiente(false, 0));
}

void test_envia_en_orden_y_quita_al_confirmar() {
    ColaEnvio<4> cola;
    cola.agregar(lectura(0));
    cola.agregar(lectura(1));

    TEST_ASSERT_EQUAL_UINT32(0, cola.siguiente(true, 0)->seq);
    cola.marcarEnviada(7, 0);
    TEST_ASSERT_NULL(cola.siguiente(true, 100));  // espera la confirmación

    TEST_ASSERT_TRUE(cola.confirmar(7));
    TEST_ASSERT_EQUAL_UINT32(1, cola.siguiente(true, 100)->seq);
    TEST_ASSERT_EQUAL(1, cola.tamano());
}

void test_confirmacion_de_otro_mensaje_se_ignora() {
    ColaEnvio<4> cola;
    cola.agregar(lectura(0));
    cola.marcarEnviada(7, 0);

    TEST_ASSERT_FALSE(cola.confirmar(8));
    TEST_ASSERT_EQUAL(1, cola.tamano());
}

void test_al_perder_la_conexion_se_reenvia_la_misma() {
    ColaEnvio<4> cola;
    cola.agregar(lectura(0));
    cola.marcarEnviada(7, 0);

    cola.conexionPerdida();

    TEST_ASSERT_EQUAL_UINT32(0, cola.siguiente(true, 10)->seq);
    TEST_ASSERT_FALSE(cola.confirmar(7));  // la confirmación vieja ya no cuenta
}

void test_sin_confirmacion_a_tiempo_se_reenvia() {
    ColaEnvio<4> cola;
    cola.agregar(lectura(0));
    cola.marcarEnviada(7, 1000);

    TEST_ASSERT_NULL(cola.siguiente(true, 1000 + ColaEnvio<4>::kEsperaConfirmacionMs - 1));
    TEST_ASSERT_NOT_NULL(cola.siguiente(true, 1000 + ColaEnvio<4>::kEsperaConfirmacionMs));
}

void test_espera_funciona_aunque_millis_se_desborde() {
    ColaEnvio<4> cola;
    cola.agregar(lectura(0));
    cola.marcarEnviada(7, 0xFFFFFF00u);

    TEST_ASSERT_NULL(cola.siguiente(true, 0x00000100u));
}

void test_llena_descarta_la_mas_vieja() {
    ColaEnvio<3> cola;
    for (uint32_t i = 0; i < 5; i++) cola.agregar(lectura(i));

    TEST_ASSERT_EQUAL(3, cola.tamano());
    TEST_ASSERT_EQUAL_UINT32(2, cola.descartadas());
    TEST_ASSERT_EQUAL_UINT32(2, cola.siguiente(true, 0)->seq);
}

void test_descartar_la_que_estaba_en_vuelo_anula_su_confirmacion() {
    ColaEnvio<2> cola;
    cola.agregar(lectura(0));
    cola.agregar(lectura(1));
    cola.marcarEnviada(7, 0);

    cola.agregar(lectura(2));  // descarta la 0, que estaba en vuelo

    TEST_ASSERT_FALSE(cola.confirmar(7));
    TEST_ASSERT_EQUAL_UINT32(1, cola.siguiente(true, 0)->seq);
}

void test_recorre_el_arreglo_circular() {
    ColaEnvio<3> cola;
    for (uint32_t i = 0; i < 10; i++) {
        cola.agregar(lectura(i));
        cola.marcarEnviada(static_cast<int>(i + 1), 0);
        TEST_ASSERT_TRUE(cola.confirmar(static_cast<int>(i + 1)));
    }
    TEST_ASSERT_EQUAL(0, cola.tamano());
    TEST_ASSERT_NULL(cola.siguiente(true, 0));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_sin_conexion_no_entrega_nada);
    RUN_TEST(test_envia_en_orden_y_quita_al_confirmar);
    RUN_TEST(test_confirmacion_de_otro_mensaje_se_ignora);
    RUN_TEST(test_al_perder_la_conexion_se_reenvia_la_misma);
    RUN_TEST(test_sin_confirmacion_a_tiempo_se_reenvia);
    RUN_TEST(test_espera_funciona_aunque_millis_se_desborde);
    RUN_TEST(test_llena_descarta_la_mas_vieja);
    RUN_TEST(test_descartar_la_que_estaba_en_vuelo_anula_su_confirmacion);
    RUN_TEST(test_recorre_el_arreglo_circular);
    return UNITY_END();
}
