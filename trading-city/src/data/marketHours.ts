import { useSyncExternalStore } from 'react'

/**
 * Market hours for towers whose market keeps a schedule. Crypto, sports,
 * weather and the econ prints have no closed hours, so they are not listed.
 * Times are Chicago wall clock. Holidays: NYSE 2026-2027 calendar
 * (https://www.nyse.com/markets/hours-calendars). Treasury adds the bond
 * market's Columbus Day and Veterans Day closes.
 */
type Schedule = {
  label: string
  open: [number, number]
  close: [number, number]
  /** Half days: the close moves earlier. Equity early close is 1 PM ET = 12 PM CT. */
  halfClose?: [number, number]
  holidays: Set<string>
  halfDays: Set<string>
}

const NYSE_HOLIDAYS = [
  '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19',
  '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
  '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18',
  '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24',
]
const NYSE_HALF_DAYS = ['2026-11-27', '2026-12-24', '2027-11-26']
const BOND_EXTRA = ['2026-10-12', '2026-11-11', '2027-10-11', '2027-11-11']

const STOCKS: Schedule = {
  label: 'stock market',
  open: [8, 30],
  close: [15, 0],
  halfClose: [12, 0],
  holidays: new Set(NYSE_HOLIDAYS),
  halfDays: new Set(NYSE_HALF_DAYS),
}

/** The 10-year tower's own window: 9:00 ET to 15 minutes before 3:30 PM ET. */
const TREASURY: Schedule = {
  label: 'bond window',
  open: [8, 0],
  close: [14, 15],
  halfClose: [12, 0],
  holidays: new Set([...NYSE_HOLIDAYS, ...BOND_EXTRA]),
  halfDays: new Set(NYSE_HALF_DAYS),
}

const BY_TOWER: Record<string, Schedule> = {
  nasdaq: STOCKS,
  'qqq-momentum': STOCKS,
  'kalshi-sp': STOCKS,
  'kalshi-sized': STOCKS,
  'treasury-10y': TREASURY,
}

const ZONE = 'America/Chicago'
const fmt = new Intl.DateTimeFormat('en-US', {
  timeZone: ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  weekday: 'short',
})

function chicagoParts(at: Date) {
  const p: Record<string, string> = {}
  for (const part of fmt.formatToParts(at)) p[part.type] = part.value
  return {
    y: Number(p.year),
    m: Number(p.month),
    d: Number(p.day),
    hh: Number(p.hour),
    mm: Number(p.minute),
    weekday: p.weekday,
  }
}

/** Chicago wall clock → instant. Two passes settle the DST offset. */
function chicagoInstant(y: number, m: number, d: number, hh: number, mm: number): Date {
  const want = Date.UTC(y, m - 1, d, hh, mm)
  let guess = want + 6 * 3600_000
  for (let i = 0; i < 2; i++) {
    const p = chicagoParts(new Date(guess))
    const seen = Date.UTC(p.y, p.m - 1, p.d, p.hh, p.mm)
    guess += want - seen
  }
  return new Date(guess)
}

function dayKey(y: number, m: number, d: number) {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

export type MarketSession = {
  open: boolean
  /** When it next opens (null while open). */
  opensAt: Date | null
  label: string
}

/** Null for towers that never close. */
export function marketSession(botId: string, now: Date = new Date()): MarketSession | null {
  const sched = BY_TOWER[botId]
  if (!sched) return null
  const today = chicagoParts(now)
  for (let ahead = 0; ahead < 14; ahead++) {
    // Walk calendar days in Chicago. Noon avoids DST edges.
    const probe = chicagoInstant(today.y, today.m, today.d, 12, 0)
    const day = chicagoParts(new Date(probe.getTime() + ahead * 86400_000))
    const key = dayKey(day.y, day.m, day.d)
    if (day.weekday === 'Sat' || day.weekday === 'Sun' || sched.holidays.has(key)) continue
    const opens = chicagoInstant(day.y, day.m, day.d, sched.open[0], sched.open[1])
    const [ch, cm] = sched.halfDays.has(key) && sched.halfClose ? sched.halfClose : sched.close
    const closes = chicagoInstant(day.y, day.m, day.d, ch, cm)
    if (now < opens) return { open: false, opensAt: opens, label: sched.label }
    if (now < closes) return { open: true, opensAt: null, label: sched.label }
  }
  return { open: false, opensAt: null, label: sched.label }
}

export function marketClosed(botId: string, now: Date = new Date()): boolean {
  const s = marketSession(botId, now)
  return Boolean(s && !s.open)
}

/** "6h 05m" until the open. Hours keep counting past a day (weekend shows 65h 30m). */
export function untilOpen(session: MarketSession | null, now: Date = new Date()): string {
  if (!session || session.open || !session.opensAt) return ''
  const mins = Math.max(0, Math.ceil((session.opensAt.getTime() - now.getTime()) / 60_000))
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `${h}h ${String(m).padStart(2, '0')}m`
}

// One shared clock for every tower and card, so 31 towers do not each run a timer.
let nowMs = Date.now()
const listeners = new Set<() => void>()
let timer: number | undefined

function subscribe(fn: () => void) {
  listeners.add(fn)
  if (timer == null) {
    timer = window.setInterval(() => {
      nowMs = Date.now()
      listeners.forEach((l) => l())
    }, 20_000)
  }
  return () => {
    listeners.delete(fn)
    if (!listeners.size && timer != null) {
      window.clearInterval(timer)
      timer = undefined
    }
  }
}

/** Current time, ticking every 20 seconds. */
export function useMarketNow(): Date {
  const ms = useSyncExternalStore(subscribe, () => nowMs)
  return new Date(ms)
}
