import { useState } from 'react'
import type { Desk } from '../types'
import { money } from '../data/format'
import {
  LEGEND,
  bannerFacts,
  centralClock,
  dataAgeSec,
  isStale,
  shortDuration,
  stockHoursLine,
} from '../data/cityRules'

type Props = {
  desk?: Desk
  limits?: Record<string, unknown>
  cachedAt?: number | null
  updatedAt?: number | null
  now: Date
}

/**
 * City banner: real money off, desk day and lifetime (losses included), the
 * daily stop distance, open count and open risk, the clock, and data age.
 * Plain words only. No screens on the towers; this is a strip on the page.
 */
export function CityBanner({ desk, limits, cachedAt, updatedAt, now }: Props) {
  const [legend, setLegend] = useState(false)
  const f = bannerFacts(desk, limits)
  const age = dataAgeSec(cachedAt, updatedAt, now.getTime())
  const stale = isStale(age)
  const lifeWins = f.lifetime_wins || 0
  const lifeLosses = f.lifetime_losses || 0
  return (
    <section className="city-banner" aria-label="Desk summary">
      {f.halted && (
        <div className="city-halted" role="alert">
          Desk halted. {f.halt_reason || 'The desk stop fired. New buys stay off until the next Chicago day.'}
        </div>
      )}
      <ul className="city-banner-row">
        <li className="city-chip money-off">Real money: off</li>
        <li className={`city-chip tone-${(f.today || 0) > 0 ? 'up' : (f.today || 0) < 0 ? 'down' : 'flat'}`}>
          Desk today {money(f.today || 0, true)}
        </li>
        {f.lifetime_realized != null && (
          <li className="city-chip" title="Every settled trade, wins and losses.">
            Lifetime {money(f.lifetime_realized, true)} ({lifeWins} won, {lifeLosses} lost)
          </li>
        )}
        <li className="city-chip" title="How much more the desk can lose today before new buys stop.">
          Stop {money(f.stop_left || 0)} left of {money(f.stop || 150)}
        </li>
        <li className="city-chip">
          Open {f.open_count || 0} of {f.max_open || 12}
        </li>
        <li className="city-chip">
          Risk {money(f.open_risk || 0)} of {money(f.max_open_risk || 100)}
        </li>
        <li className="city-chip">
          {centralClock(now)} · {stockHoursLine(now)}
        </li>
        {age != null && (
          <li className={`city-chip ${stale ? 'stale' : ''}`} aria-live="polite">
            {stale ? 'STALE · ' : ''}data is {shortDuration(age)} old
          </li>
        )}
        <li>
          <button
            type="button"
            className="city-chip city-chip-btn"
            aria-expanded={legend}
            onClick={() => setLegend((v) => !v)}
          >
            Legend
          </button>
        </li>
        <li>
          <a className="city-chip city-chip-btn" href={`${import.meta.env.BASE_URL}guide.html`} target="_blank" rel="noreferrer">
            Guide
          </a>
        </li>
      </ul>
      {legend && (
        <ul className="city-legend" aria-label="What the colors and lights mean">
          {LEGEND.map((row) => (
            <li key={row.words}>
              <i style={{ background: row.swatch }} aria-hidden />
              {row.words}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
