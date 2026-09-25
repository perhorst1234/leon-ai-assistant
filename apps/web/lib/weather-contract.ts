export type WeatherCondition = { label: string; category: 'clear' | 'cloud' | 'fog' | 'rain' | 'snow' | 'storm' | 'unknown' };
export type WeatherDay = {
  date: string; weather_code: number; condition: WeatherCondition;
  temperature_min_c: number; temperature_max_c: number; precipitation_probability_percent: number;
  sunrise: string; sunset: string;
};
export type WeatherStatus = {
  status: 'available'; location: { label: 'Amsterdam'; timezone: 'Europe/Amsterdam' };
  current: {
    time: string; temperature_c: number; apparent_temperature_c: number;
    relative_humidity_percent: number; precipitation_mm: number; cloud_cover_percent: number;
    wind_speed_kmh: number; weather_code: number; condition: WeatherCondition;
  };
  forecast: WeatherDay[];
  source: { provider: 'Open-Meteo'; documentation_url: 'https://open-meteo.com/en/docs'; licence: 'CC BY 4.0'; retrieved_at: string; note: string };
  cache: 'hit' | 'miss'; permission_check_id?: string;
};

const object = (value: unknown): Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const finite = (value: unknown, minimum: number, maximum: number) => typeof value === 'number' && Number.isFinite(value) && value >= minimum && value <= maximum ? value : undefined;
const integer = (value: unknown, minimum: number, maximum: number) => Number.isInteger(value) && (value as number) >= minimum && (value as number) <= maximum ? value as number : undefined;
const isoDate = /^\d{4}-\d{2}-\d{2}$/;
const isoMinute = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
const categories = new Set(['clear', 'cloud', 'fog', 'rain', 'snow', 'storm', 'unknown']);
const labels = new Set(['Helder', 'Licht bewolkt', 'Bewolkt', 'Mist', 'Motregen', 'Regen', 'Sneeuw', 'Buien', 'Onweer', 'Onbekend']);

function condition(value: unknown): WeatherCondition | undefined {
  const item = object(value), label = item.label, category = item.category;
  return typeof label === 'string' && labels.has(label) && typeof category === 'string' && categories.has(category)
    ? { label, category: category as WeatherCondition['category'] } : undefined;
}

export function normalizeWeather(input: unknown): WeatherStatus {
  const root = object(input), location = object(root.location), current = object(root.current), source = object(root.source);
  const currentCondition = condition(current.condition);
  const forecastInput = Array.isArray(root.forecast) ? root.forecast : [];
  if (root.status !== 'available' || location.label !== 'Amsterdam' || location.timezone !== 'Europe/Amsterdam'
    || typeof current.time !== 'string' || !isoMinute.test(current.time) || !currentCondition
    || source.provider !== 'Open-Meteo' || source.documentation_url !== 'https://open-meteo.com/en/docs'
    || source.licence !== 'CC BY 4.0' || typeof source.retrieved_at !== 'string' || typeof source.note !== 'string'
    || !['hit', 'miss'].includes(String(root.cache)) || forecastInput.length !== 3) throw new Error('Ongeldig weerantwoord.');
  const normalizedCurrent = {
    time: current.time,
    temperature_c: finite(current.temperature_c, -100, 70),
    apparent_temperature_c: finite(current.apparent_temperature_c, -100, 70),
    relative_humidity_percent: integer(current.relative_humidity_percent, 0, 100),
    precipitation_mm: finite(current.precipitation_mm, 0, 500),
    cloud_cover_percent: integer(current.cloud_cover_percent, 0, 100),
    wind_speed_kmh: finite(current.wind_speed_kmh, 0, 500),
    weather_code: integer(current.weather_code, 0, 99),
    condition: currentCondition,
  };
  if (Object.values(normalizedCurrent).some(value => value === undefined)) throw new Error('Ongeldig weerantwoord.');
  const forecast = forecastInput.map(value => {
    const day = object(value), dayCondition = condition(day.condition);
    const normalized = {
      date: typeof day.date === 'string' && isoDate.test(day.date) ? day.date : undefined,
      weather_code: integer(day.weather_code, 0, 99), condition: dayCondition,
      temperature_min_c: finite(day.temperature_min_c, -100, 70), temperature_max_c: finite(day.temperature_max_c, -100, 70),
      precipitation_probability_percent: integer(day.precipitation_probability_percent, 0, 100),
      sunrise: typeof day.sunrise === 'string' && isoMinute.test(day.sunrise) ? day.sunrise : undefined,
      sunset: typeof day.sunset === 'string' && isoMinute.test(day.sunset) ? day.sunset : undefined,
    };
    if (Object.values(normalized).some(item => item === undefined) || (normalized.temperature_min_c as number) > (normalized.temperature_max_c as number)) throw new Error('Ongeldig weerantwoord.');
    return normalized as WeatherDay;
  });
  return {
    status: 'available', location: { label: 'Amsterdam', timezone: 'Europe/Amsterdam' },
    current: normalizedCurrent as WeatherStatus['current'], forecast,
    source: { provider: 'Open-Meteo', documentation_url: 'https://open-meteo.com/en/docs', licence: 'CC BY 4.0', retrieved_at: source.retrieved_at, note: source.note.slice(0, 180) },
    cache: root.cache as 'hit' | 'miss', permission_check_id: typeof root.permission_check_id === 'string' ? root.permission_check_id : undefined,
  };
}
