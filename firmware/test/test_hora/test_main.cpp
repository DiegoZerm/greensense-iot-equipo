#include <hora.h>
#include <unity.h>

using namespace gs;

constexpr int64_t kAhora = 1793548800;  // 2026-11-01T16:00:00Z

void setUp() {}
void tearDown() {}

void test_lectura_con_hora_no_cambia() {
    Lectura l;
    l.ts = kAhora - 100;
    TEST_ASSERT_TRUE(completarHora(l, kAhora, 5000));
    TEST_ASSERT_EQUAL_INT64(kAhora - 100, l.ts);
}

void test_lectura_tomada_sin_hora_se_completa_al_sincronizar() {
    Lectura l;
    l.msCaptura = 10000;
    TEST_ASSERT_TRUE(completarHora(l, kAhora, 70000));  // 60 s después
    TEST_ASSERT_EQUAL_INT64(kAhora - 60, l.ts);
}

void test_sin_hora_valida_no_se_completa() {
    Lectura l;
    l.msCaptura = 1000;
    TEST_ASSERT_FALSE(completarHora(l, 120, 5000));  // reloj todavía en 1970
    TEST_ASSERT_EQUAL_INT64(0, l.ts);
}

void test_funciona_aunque_millis_se_desborde() {
    Lectura l;
    l.msCaptura = 0xFFFFF000u;
    TEST_ASSERT_TRUE(completarHora(l, kAhora, 0x00001000u));  // 8.192 s después
    TEST_ASSERT_EQUAL_INT64(kAhora - 8, l.ts);
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_lectura_con_hora_no_cambia);
    RUN_TEST(test_lectura_tomada_sin_hora_se_completa_al_sincronizar);
    RUN_TEST(test_sin_hora_valida_no_se_completa);
    RUN_TEST(test_funciona_aunque_millis_se_desborde);
    return UNITY_END();
}
