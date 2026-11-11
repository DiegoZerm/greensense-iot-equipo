import { formatear, hoyLocal, inicioDelDia, isoLocal, sumarDias } from './tiempo';

describe('tiempo en la hora del invernadero', () => {
  it('hoy usa la fecha de México aunque en UTC ya sea mañana', () => {
    // 2 nov 22:30 en México son las 04:30 UTC del 3 nov.
    expect(hoyLocal(new Date('2026-11-03T04:30:00Z'))).toBe('2026-11-02');
  });

  it('la medianoche local es a las 06:00 UTC', () => {
    expect(inicioDelDia('2026-11-02').toISOString()).toBe('2026-11-02T06:00:00.000Z');
  });

  it('suma días cruzando el fin de mes', () => {
    expect(sumarDias('2026-10-30', 3)).toBe('2026-11-02');
    expect(sumarDias('2026-11-01', -1)).toBe('2026-10-31');
  });

  it('arma el ISO con el desfase local', () => {
    expect(isoLocal(new Date('2026-11-02T06:00:00Z'))).toBe('2026-11-02T00:00:00-06:00');
  });

  it('formatea en español y en la hora local', () => {
    expect(
      formatear(Date.parse('2026-11-02T21:05:00Z'), {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }),
    ).toBe('15:05');
  });
});
