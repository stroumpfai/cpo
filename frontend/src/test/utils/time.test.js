// Pin timezone so conversion math is deterministic
process.env.TZ = 'Europe/Zurich';

import { localHhmmToUtc, utcHhmmToLocal, parseUtcDt } from '../../utils/time.js';

describe('localHhmmToUtc', () => {
  it('converts 14:00 local (UTC+2 summer) to 12:00 UTC', () => {
    expect(localHhmmToUtc('2024-06-15', '14:00')).toBe('12:00');
  });

  it('handles midnight rollover: 00:30 local (UTC+2) becomes 22:30 UTC', () => {
    // 00:30 local in UTC+2 is 22:30 of the previous day — only HH:MM is returned
    expect(localHhmmToUtc('2024-06-15', '00:30')).toBe('22:30');
  });
});

describe('utcHhmmToLocal', () => {
  it('converts 12:00 UTC to 14:00 local (UTC+2 summer)', () => {
    expect(utcHhmmToLocal('2024-06-15', '12:00')).toBe('14:00');
  });
});

describe('round-trip', () => {
  it('localToUtc then utcToLocal gives back the same time', () => {
    const date = '2024-06-15';
    const localTime = '14:00';
    const utcTime = localHhmmToUtc(date, localTime);
    const restored = utcHhmmToLocal(date, utcTime);
    expect(restored).toBe(localTime);
  });
});

describe('parseUtcDt', () => {
  it('returns the correct UTC epoch-ms for a UTC date+time', () => {
    expect(parseUtcDt('2024-01-01', '00:00')).toBe(Date.UTC(2024, 0, 1, 0, 0));
  });
});
