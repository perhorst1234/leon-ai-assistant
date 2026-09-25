import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeWeather } from '../lib/weather-contract.ts';

const valid = () => ({
  status: 'available', cache: 'miss', permission_check_id: 'connector-check-1',
  location: { label: 'Amsterdam', timezone: 'Europe/Amsterdam', latitude: 52.3676, longitude: 4.9041 },
  current: { time: '2026-09-25T17:00', temperature_c: 18.4, apparent_temperature_c: 17.2, relative_humidity_percent: 61, precipitation_mm: 0, cloud_cover_percent: 45, wind_speed_kmh: 13.7, weather_code: 2, condition: { label: 'Licht bewolkt', category: 'cloud' } },
  forecast: [
    { date: '2026-09-25', weather_code: 2, condition: { label: 'Licht bewolkt', category: 'cloud' }, temperature_min_c: 11, temperature_max_c: 19, precipitation_probability_percent: 10, sunrise: '2026-09-25T07:31', sunset: '2026-09-25T19:30' },
    { date: '2026-09-26', weather_code: 61, condition: { label: 'Regen', category: 'rain' }, temperature_min_c: 10.5, temperature_max_c: 17.5, precipitation_probability_percent: 75, sunrise: '2026-09-26T07:33', sunset: '2026-09-26T19:28' },
    { date: '2026-09-27', weather_code: 3, condition: { label: 'Bewolkt', category: 'cloud' }, temperature_min_c: 9, temperature_max_c: 16, precipitation_probability_percent: 30, sunrise: '2026-09-27T07:35', sunset: '2026-09-27T19:25' },
  ],
  source: { provider: 'Open-Meteo', documentation_url: 'https://open-meteo.com/en/docs', licence: 'CC BY 4.0', retrieved_at: '2026-09-25T15:00:00+00:00', note: 'Model forecast.' },
});

test('normalizes the fixed bounded Amsterdam weather contract', () => {
  const result = normalizeWeather(valid());
  assert.equal(result.location.label, 'Amsterdam');
  assert.equal(result.current.temperature_c, 18.4);
  assert.equal(result.forecast.length, 3);
  assert.equal(result.forecast[1].condition.label, 'Regen');
  assert.equal(result.source.documentation_url, 'https://open-meteo.com/en/docs');
  assert.equal('latitude' in result.location, false);
});

test('rejects malformed, oversized or provider-controlled weather shapes', () => {
  for (const mutate of [
    value => { value.current.temperature_c = Number.NaN; },
    value => { value.forecast.pop(); },
    value => { value.current.condition.label = '<script>'; },
    value => { value.source.documentation_url = 'https://evil.invalid'; },
    value => { value.location.label = 'caller-selected'; },
  ]) {
    const value = valid(); mutate(value);
    assert.throws(() => normalizeWeather(value), /Ongeldig weerantwoord/);
  }
});
