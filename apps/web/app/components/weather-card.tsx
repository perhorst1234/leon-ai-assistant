'use client';

import { useEffect, useRef, useState } from 'react';
import { CloudRain, CloudSun, Droplets, ExternalLink, Wind } from 'lucide-react';
import { normalizeWeather, type WeatherStatus } from '../../lib/weather-contract';
import './weather-card.css';

const errorText = (value: unknown) => value && typeof value === 'object' && 'error' in value && typeof value.error === 'string' ? value.error : 'Weer niet bereikbaar.';
async function fetchWeather(token: string, signal: AbortSignal) {
  const response = await fetch('/api/leon?resource=weather-current', { signal, cache: 'no-store', headers: { Authorization: `Bearer ${token}` } });
  const body: unknown = await response.json();
  if (!response.ok) throw new Error(errorText(body));
  return normalizeWeather(body);
}
const dayLabel = (date: string) => new Intl.DateTimeFormat('nl-NL', { weekday: 'short', timeZone: 'Europe/Amsterdam' }).format(new Date(`${date}T12:00:00Z`));

export default function WeatherCard({ token, refreshId }: { token: string; refreshId: number }) {
  const [weather, setWeather] = useState<WeatherStatus | null>(null);
  const [error, setError] = useState('');
  const version = useRef(0);
  useEffect(() => {
    const controller = new AbortController(), current = ++version.current;
    fetchWeather(token, controller.signal).then(value => {
      if (!controller.signal.aborted && current === version.current) { setWeather(value); setError(''); }
    }).catch(reason => {
      if (!controller.signal.aborted && current === version.current) { setWeather(null); setError(reason instanceof Error ? reason.message : 'Weer niet bereikbaar.'); }
    });
    return () => controller.abort();
  }, [token, refreshId]);
  if (error) return <section className="weather-card" aria-label="Weer in Amsterdam"><header><CloudSun size={18}/><h2>Weer in Amsterdam</h2></header><p className="work-error" role="alert">{error}</p></section>;
  if (!weather) return <section className="weather-card" aria-label="Weer in Amsterdam"><header><CloudSun size={18}/><h2>Weer in Amsterdam</h2></header><p className="work-hint">Actueel weer laden…</p></section>;
  return <section className="weather-card" aria-label="Weer in Amsterdam">
    <header><CloudSun size={18}/><div><h2>Weer in Amsterdam</h2><p>{weather.current.condition.label} · modelverwachting</p></div><strong>{weather.current.temperature_c.toFixed(1)}°</strong></header>
    <div className="weather-now"><span><CloudRain size={14}/> Voelt als {weather.current.apparent_temperature_c.toFixed(1)}°</span><span><Droplets size={14}/> {weather.current.relative_humidity_percent}% · {weather.current.precipitation_mm.toFixed(1)} mm</span><span><Wind size={14}/> {weather.current.wind_speed_kmh.toFixed(1)} km/u</span></div>
    <div className="weather-days">{weather.forecast.map(day => <article key={day.date}><strong>{dayLabel(day.date)}</strong><span>{day.condition.label}</span><em>{day.temperature_min_c.toFixed(0)}° / {day.temperature_max_c.toFixed(0)}°</em><small>{day.precipitation_probability_percent}% regen</small></article>)}</div>
    <footer><span>{weather.cache === 'hit' ? '10-minutencache' : 'zojuist opgehaald'}</span><a href={weather.source.documentation_url} target="_blank" rel="noreferrer">Open-Meteo · {weather.source.licence} <ExternalLink size={12}/></a></footer>
  </section>;
}
