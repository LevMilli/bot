// Look rules for APEX-CITY (plan 856-859, 877). Run: npm test
import assert from 'node:assert/strict'
import test from 'node:test'
import { loadData } from './load-ts.mjs'

const { format, cityRules: r } = await loadData(['format', 'cityRules'])

const desk = (o = {}) => ({ id: 'btc15m', name: 'BTC 15m', present: true, ...o })
const shadow = (o = {}) => ({ id: 'new-twin', name: 'New twin', present: true, shadow_only: true, ...o })

test('closed and paused towers render black with blacked-out windows', () => {
  for (const bot of [desk({ paused: true }), desk({ present: false })]) {
    assert.equal(format.towerClosed(bot), true)
    assert.equal(r.roofColor(bot), '#000000')
    assert.equal(r.windowLitShare(bot), 0)
  }
  // Blacked-out panes are near black, not slate gray.
  const hex = r.BLACKED_OUT.replace('#', '')
  const lum = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16)).reduce((a, b) => a + b, 0)
  assert.ok(lum < 30, `blacked-out color too bright: ${r.BLACKED_OUT}`)
})

test('market-closed towers are black too (roof and windows)', () => {
  const bot = desk({ today: 12 })
  assert.equal(r.roofColor(bot, true), '#000000')
  assert.equal(r.windowLitShare(bot, true), 0)
})

test('inactive practice towers stay hidden until they trade', () => {
  assert.equal(format.towerInCity(shadow()), false)
  assert.equal(format.towerInCity(shadow({ realized: 0, today: 0, open_count: 0, trades: [], history: [] })), false)
  assert.deepEqual(r.hiddenLot([shadow(), desk()]).map((b) => b.id), ['new-twin'])
  // Wakes on any real activity.
  assert.equal(format.towerInCity(shadow({ open_count: 1 })), true)
  assert.equal(format.towerInCity(shadow({ history: [{ pnl: 0 }] })), true)
  assert.equal(format.towerInCity(shadow({ realized: -3 })), true)
  assert.equal(format.towerInCity(shadow({ lifetime: { trades: 2 } })), true)
  // Desk towers and research landmarks always stand.
  assert.equal(format.towerInCity(desk()), true)
  assert.equal(format.towerInCity(shadow({ id: 'calibration-lab' })), true)
})

test('roof color follows today: green up, red down, gray flat', () => {
  assert.equal(r.roofColor(desk({ today: 4.2 })), r.ROOF_UP)
  assert.equal(r.roofColor(desk({ today: -1 })), r.ROOF_DOWN)
  assert.equal(r.roofColor(desk({ today: 0 })), r.ROOF_FLAT)
  assert.equal(r.roofColor(desk({ today: 0, card: { today: { pnl: -2 } } })), r.ROOF_DOWN)
})

test('windows light up with today\'s trade count', () => {
  const quiet = r.windowLitShare(desk({ card: { trades_today: 0 } }))
  const busy = r.windowLitShare(desk({ card: { trades_today: 6 } }))
  assert.ok(quiet > 0 && quiet < busy)
  assert.ok(r.windowLitShare(desk({ card: { trades_today: 99 } })) <= 1)
})

test('tower height follows lifetime results and is capped', () => {
  const base = r.towerHeight(desk(), 1)
  const rich = r.towerHeight(desk({ lifetime: { realized: 100000 } }), 1)
  const poor = r.towerHeight(desk({ lifetime: { realized: -100000 } }), 1)
  assert.ok(rich > base && poor < base)
  assert.ok(rich - base <= 3 + 1e-9 && base - poor <= 1.5 + 1e-9)
})

test('banner totals include losses and show stop distance, open count and risk', () => {
  const f = r.bannerFacts(
    { today: -40, open_count: 5, open_risk: 62.5, lifetime: { realized: -12, wins: 3, losses: 9 } },
    { daily_loss_stop: 150, max_open_positions: 12, max_open_risk: 100 },
  )
  assert.equal(f.real_money, 'off')
  assert.equal(f.today, -40)
  assert.equal(f.lifetime_realized, -12)
  assert.equal(f.lifetime_losses, 9)
  assert.equal(f.stop_left, 110)
  assert.equal(f.max_open, 12)
  assert.equal(f.max_open_risk, 100)
  const halted = r.bannerFacts({ today: -150, gate: 'Daily loss stop is hit ($150.00 against $150.00).' }, {})
  assert.equal(halted.halted, true)
  assert.equal(halted.stop_left, 0)
})

test('csv export keeps losing trades', () => {
  const csv = r.tradesCsv(desk({ history: [{ what: 'A, b', pnl: 2 }, { what: 'C', pnl: -3.5 }], positions: [{ what: 'D' }] }))
  const lines = csv.trim().split('\n')
  assert.equal(lines.length, 4)
  assert.ok(lines.some((l) => l.includes('-3.5')))
  assert.ok(lines[1].includes('"A, b"'))
})

test('timer labels, countdown, stale stamp, quiet hours and search', () => {
  assert.equal(r.timerLabel(desk({ card: { every_sec: 60 } })), 'every 60s')
  assert.equal(r.timerLabel(desk({ card: { every_sec: 300 } })), 'every 5 min')
  assert.equal(r.timerLabel(desk({ card: { scan_times: ['12:05', '13:05'] } })), 'scans at 12:05, 13:05 CT')
  assert.equal(r.nextCheckIn(desk({ card: { next_check_in_sec: 90 } }), 30), 'next check in 1m')
  assert.equal(r.nextCheckIn(desk({ card: { next_check_in_sec: 10 } }), 30), 'next check due now')
  const now = Date.UTC(2026, 10, 13, 18, 0, 0)
  assert.equal(r.isStale(r.dataAgeSec(now / 1000 - 301, null, now)), true)
  assert.equal(r.isStale(r.dataAgeSec(now / 1000 - 20, null, now)), false)
  // 23:30 CT and 06:30 CT are quiet; noon CT is not.
  assert.equal(r.isQuietHours(new Date(Date.UTC(2026, 10, 14, 5, 30))), true)
  assert.equal(r.isQuietHours(new Date(Date.UTC(2026, 10, 13, 12, 30))), true)
  assert.equal(r.isQuietHours(new Date(Date.UTC(2026, 10, 13, 18, 0))), false)
  assert.deepEqual(r.searchTowers([desk(), shadow()], 'twin').map((b) => b.id), ['new-twin'])
})

test('progress bar only on practice towers, toward 50', () => {
  assert.equal(r.resultsProgress(desk()), null)
  const p = r.resultsProgress(shadow({ card: { progress: { have: 20, need: 50, note: '20 of 50' } } }))
  assert.equal(p.pct, 40)
})
