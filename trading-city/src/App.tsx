import { AdaptiveDpr, AdaptiveEvents } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useSnapshot } from './data/useSnapshot'
import { Banners } from './hud/Banners'
import { Monitors } from './hud/Monitors'
import { Ticker } from './hud/Ticker'
import { TowerRail } from './hud/TowerRail'
import { beamColorFor } from './data/format'
import { FLOORS, parseCityHash } from './data/floorMap'
import { CityScene } from './scene/CityScene'
import { OfficeHallScene } from './scene/OfficeHallScene'
import { BankScene } from './scene/BankScene'
import { BossDashboard } from './hud/BossDashboard'
import type { BotRow } from './types'

type View = 'city' | 'bank' | 'office'
type FloorFocus = 'suite' | 'hall' | 'boss'

function FloorNavMenu({
  bots,
  selected,
  fromBank,
  floorFocus,
  bossOpen,
  onSuite,
  onHall,
  onBoss,
  onPickBot,
}: {
  bots: BotRow[]
  selected: BotRow
  fromBank: boolean
  floorFocus: FloorFocus
  bossOpen: boolean
  onSuite: () => void
  onHall: () => void
  onBoss: () => void
  onPickBot: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const kind = fromBank ? 'Tellers' : 'Floor'
  const label =
    bossOpen || floorFocus === 'boss'
      ? `${kind} · Boss office`
      : floorFocus === 'hall'
        ? `${kind} · Hallway`
        : `${kind} · ${selected.name}`

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null
      if (t?.closest?.('.floor-nav')) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    // click (not mousedown): mousedown-outside can race the option's click
    // and close/unmount the panel before onHall/onBoss runs.
    document.addEventListener('click', onDoc)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onDoc)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  const pick = (fn: () => void) => (e: { preventDefault(): void; stopPropagation(): void }) => {
    e.preventDefault()
    e.stopPropagation()
    fn()
    setOpen(false)
  }

  const botSection = fromBank ? 'Switch teller' : 'Tower suites'

  return (
    <div className={`floor-nav${open ? ' open' : ''}`}>
      <button
        type="button"
        className="floor-nav-toggle"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={open ? `Hide ${kind} menu` : `Show ${kind} menu`}
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
      >
        <span className="floor-nav-label">{label}</span>
        <span className="floor-nav-caret" aria-hidden>
          {open ? '▴' : '▾'}
        </span>
      </button>
      {open && (
        <div
          className="floor-nav-panel"
          role="listbox"
          aria-label={fromBank ? 'Teller and floor navigation' : 'Floor navigation'}
        >
          <p className="floor-nav-section">{botSection}</p>
          {bots.map((bot, i) => (
            <button
              key={bot.id}
              type="button"
              role="option"
              className={bot.id === selected.id && floorFocus === 'suite' && !bossOpen ? 'active' : ''}
              style={{ borderLeftColor: beamColorFor(bot.id, i) }}
              onClick={pick(() => onPickBot(bot.id))}
            >
              {bot.name}
            </button>
          ))}
          <p className="floor-nav-section">Floor zones</p>
          <button
            type="button"
            role="option"
            className={floorFocus === 'suite' && !bossOpen ? 'active' : ''}
            onClick={pick(onSuite)}
          >
            This suite
          </button>
          <button
            type="button"
            role="option"
            className={floorFocus === 'hall' && !bossOpen ? 'active' : ''}
            onClick={pick(onHall)}
          >
            Hallway
          </button>
          <button
            type="button"
            role="option"
            className={bossOpen || floorFocus === 'boss' ? 'active' : ''}
            onClick={pick(onBoss)}
          >
            Boss office
          </button>
        </div>
      )}
    </div>
  )
}

function guestModeFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get('guest') === '1'
  } catch {
    return false
  }
}

function applyHashRoute(
  setView: (v: View) => void,
  setSelectedId: (id: string | null) => void,
  setFromBank: (v: boolean) => void,
  setFloorFocus: (v: FloorFocus) => void,
  setBossOpen: (v: boolean) => void,
  setSpawnBotId: (id: string | null) => void,
  bots: BotRow[],
) {
  const route = parseCityHash(window.location.hash || '')
  if (route.view === 'boss') {
    // Prefer the live boss board on the office floor when a bot is available.
    const fallback = bots.find((b) => b.present !== false)?.id || bots[0]?.id || null
    if (fallback) {
      setSelectedId(fallback)
      setSpawnBotId(fallback)
      setFromBank(false)
      setFloorFocus('boss')
      setBossOpen(true)
      setView('office')
      return
    }
    setSelectedId(null)
    setFromBank(true)
    setFloorFocus('suite')
    setBossOpen(false)
    setView('bank')
    return
  }
  if (route.view === 'bank') {
    setSelectedId(null)
    setSpawnBotId(null)
    setFromBank(true)
    setFloorFocus('suite')
    setBossOpen(false)
    setView('bank')
    return
  }
  if (route.view === 'office' && route.botId) {
    setSelectedId(route.botId)
    setSpawnBotId(route.botId)
    setFromBank(true)
    setFloorFocus('suite')
    setBossOpen(false)
    setView('office')
    return
  }
  if (route.view === 'floor') {
    const id = route.botId || bots.find((b) => b.present !== false)?.id || bots[0]?.id || 'sports-gap'
    setSelectedId(id)
    setSpawnBotId(id)
    setFromBank(true)
    setFloorFocus('hall')
    setBossOpen(false)
    setView('office')
    return
  }
  setSelectedId(null)
  setSpawnBotId(null)
  setFromBank(false)
  setFloorFocus('suite')
  setBossOpen(false)
  setView('city')
}

export default function App() {
  const { snap, mode, error, loading, updatedAt, connectLive } = useSnapshot()
  const [view, setView] = useState<View>('city')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [fromBank, setFromBank] = useState(false)
  const [screensOpen, setScreensOpen] = useState(false)
  const [floorFocus, setFloorFocus] = useState<FloorFocus>('suite')
  const [bossOpen, setBossOpen] = useState(false)
  const [spawnBotId, setSpawnBotId] = useState<string | null>(null)
  /** Desk ops HUD (skips / budgets / adapt / fill tax) — opens from ledger/compliance click. */
  const [vaultOpsOpen, setVaultOpsOpen] = useState(false)
  const [walkHint, setWalkHint] = useState('')
  const guest = useMemo(() => guestModeFromUrl(), [])

  const bots = snap?.bots || []
  const selected: BotRow | null = useMemo(
    () => bots.find((b) => b.id === selectedId) || null,
    [bots, selectedId],
  )

  // Keep a ref so hash routing can read latest bots without re-applying on every
  // snapshot poll (re-apply was resetting floorFocus → suite and closing the hall).
  const botsRef = useRef(bots)
  botsRef.current = bots

  useEffect(() => {
    const apply = () =>
      applyHashRoute(
        setView,
        setSelectedId,
        setFromBank,
        setFloorFocus,
        setBossOpen,
        setSpawnBotId,
        botsRef.current,
      )
    apply()
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [])

  // Deep-link #/boss once bots exist (hash effect alone may run before fixture load).
  useEffect(() => {
    if (!bots.length) return
    if (parseCityHash(window.location.hash || '').view !== 'boss') return
    applyHashRoute(setView, setSelectedId, setFromBank, setFloorFocus, setBossOpen, setSpawnBotId, bots)
  }, [bots.length])

  const openVault = () => {
    setSelectedId(null)
    setSpawnBotId(null)
    setFromBank(true)
    setFloorFocus('suite')
    setBossOpen(false)
    setView('bank')
    window.location.hash = '#/bank'
  }

  const openTeller = (id: string) => {
    setSelectedId(id)
    setSpawnBotId(id)
    setFromBank(true)
    setFloorFocus('suite')
    setBossOpen(false)
    setView('office')
    window.location.hash = `#/office/${id}`
  }

  const openTower = (id: string) => {
    setSelectedId(id)
    setSpawnBotId(id)
    setFromBank(false)
    setFloorFocus('suite')
    setBossOpen(false)
    setView('office')
    window.location.hash = `#/office/${id}`
  }

  useEffect(() => {
    setScreensOpen(false)
  }, [selectedId, view])

  useEffect(() => {
    if (view !== 'bank') {
      setVaultOpsOpen(false)
      setWalkHint('')
    }
  }, [view])

  const backToCity = () => {
    setSelectedId(null)
    setSpawnBotId(null)
    setFromBank(false)
    setFloorFocus('suite')
    setBossOpen(false)
    setVaultOpsOpen(false)
    setView('city')
    window.location.hash = '#/plaza'
  }

  const backToBank = () => {
    setSelectedId(null)
    setSpawnBotId(null)
    setFromBank(true)
    setFloorFocus('suite')
    setBossOpen(false)
    setView('bank')
    window.location.hash = '#/bank'
  }

  return (
    <div className={`app ${view !== 'city' ? 'office' : 'city'}${guest ? ' guest' : ''}`}>
      <div className="stage">
        <Canvas
          dpr={view === 'bank' ? [1, 1.75] : [1, 1.25]}
          gl={{
            antialias: view === 'bank',
            alpha: false,
            powerPreference: 'high-performance',
          }}
          camera={{ position: [0, 12, 14], fov: 46 }}
          performance={{ min: 0.45 }}
        >
          <AdaptiveDpr pixelated />
          <AdaptiveEvents />
          <Suspense fallback={null}>
            {view === 'office' && selected && spawnBotId ? (
              <OfficeHallScene
                bot={selected}
                bots={bots}
                desk={snap?.desk}
                spawnBotId={spawnBotId}
                spawnMode={bossOpen || floorFocus === 'boss' ? 'boss' : floorFocus === 'hall' ? 'hall' : 'suite'}
                onSelect={(id) => {
                  setSelectedId(id)
                  setFloorFocus('suite')
                  setBossOpen(false)
                  window.history.replaceState(null, '', `#/office/${id}`)
                }}
                onOpenScreens={() => setScreensOpen(true)}
                onWalkHint={setWalkHint}
              />
            ) : view === 'bank' ? (
              <BankScene
                bots={bots}
                desk={snap?.desk}
                onSelectTeller={openTeller}
                onOpenDeskOps={() => setVaultOpsOpen(true)}
                onWalkHint={setWalkHint}
              />
            ) : (
              <CityScene
                bots={bots}
                desk={snap?.desk}
                selectedId={selectedId}
                onSelect={openTower}
                onOpenVault={openVault}
              />
            )}
          </Suspense>
        </Canvas>

        <header className="chrome-top">
          <div className="brand-block">
            <h1 className="brand">APEX-CITY</h1>
            <p className="tagline">
              {guest
                ? 'Guest read-only · paper desk · no staff actions'
                : view === 'bank'
                  ? 'Neon paper trust · dual banks · aisle to vault'
                  : view === 'office' && fromBank
                    ? 'Teller desk · paper trades · switch windows'
                    : 'Neon paper desk · towers · live snapshot'}
            </p>
          </div>
          <div className="chrome-actions">
            {view === 'office' ? (
              <>
                {fromBank && (
                  <button type="button" className="back-btn" onClick={backToBank}>
                    ← Back to bank
                  </button>
                )}
                <button type="button" className="back-btn ghost" onClick={backToCity}>
                  ← Go to city
                </button>
              </>
            ) : view !== 'city' ? (
              <button type="button" className="back-btn" onClick={backToCity}>
                ← Go to city
              </button>
            ) : guest ? null : (
              <a className="back-btn ghost" href="/pimp-trading">
                PIMP-TRADING
              </a>
            )}
            {view === 'city' && (
              <button type="button" className="back-btn ghost" onClick={openVault}>
                Enter vault
              </button>
            )}
            <span className="meta">
              {guest ? 'guest · ' : ''}
              {loading && !snap
                ? 'loading…'
                : mode === 'offline'
                  ? 'offline demo'
                  : snap?.health?.alive
                    ? 'live desk · timer on'
                    : 'live desk · timer off'}
              {updatedAt ? ` · ${new Date(updatedAt).toLocaleTimeString()}` : ''}
            </span>
          </div>
        </header>

        <Banners
          mode={mode}
          paperBanner={snap?.banner}
          error={error}
          roi={snap?.roi_system}
          health={snap?.health}
          lastCheck={snap?.desk?.central_check || snap?.desk?.last_check}
          onConnect={() => void connectLive()}
          compact={view === 'bank'}
        />

        {view === 'office' && selected && (
          <div className="office-hud">
            <div className="office-hud-top">
              <FloorNavMenu
                bots={bots}
                selected={selected}
                fromBank={fromBank}
                floorFocus={floorFocus}
                bossOpen={bossOpen}
                onSuite={() => {
                  setFloorFocus('suite')
                  setBossOpen(false)
                  if (selectedId) setSpawnBotId(selectedId)
                }}
                onHall={() => {
                  setFloorFocus('hall')
                  setBossOpen(false)
                }}
                onBoss={() => {
                  setFloorFocus('boss')
                  setBossOpen(true)
                  setSpawnBotId('kalshi-sized')
                  setSelectedId('kalshi-sized')
                }}
                onPickBot={(id) => {
                  if (fromBank) openTeller(id)
                  else openTower(id)
                }}
              />
              <div className="office-title">
                <span className="screen-hint">
                  {walkHint || 'W/S walk · A/D turn · Space jump · mouse look'}
                </span>
              </div>
            </div>
            {/* Compact one-liner only in suite — no half-screen status box over the wing. */}
            {fromBank && floorFocus === 'suite' && !bossOpen && (
              <p className="teller-status-line" role="status">
                {(selected.why?.trim() ||
                  selected.idle_copy?.trim() ||
                  selected.blurb?.trim() ||
                  'Waiting on next paper check.') +
                  ` · today ${selected.today == null ? '—' : `$${Number(selected.today).toFixed(2)}`}`}
              </p>
            )}
          </div>
        )}

        {view === 'office' && bossOpen && (
          <BossDashboard
            bots={bots}
            desk={snap?.desk}
            roi={snap?.roi_system}
            snap={snap}
            onClose={() => {
              setBossOpen(false)
              setFloorFocus('hall')
            }}
            onFocusBot={(id) => {
              setSelectedId(id)
              setBossOpen(false)
              setFloorFocus('suite')
            }}
          />
        )}

        {view === 'office' && selected && screensOpen && (
          <div
            className="screen-lightbox"
            role="dialog"
            aria-label="Desk screens"
            onClick={() => setScreensOpen(false)}
          >
            <button type="button" className="back-btn screen-close" onClick={() => setScreensOpen(false)}>
              Close screens
            </button>
            <div className="screen-sheet" onClick={(e) => e.stopPropagation()}>
              <Monitors bot={selected} desk={snap?.desk} />
            </div>
          </div>
        )}

        {view === 'bank' && (
          <div className="office-hud bank-hud">
            <div className="office-title">
              <strong>APEX-CITY TRUST</strong>
              <span className={walkHint.startsWith('E') ? 'walk-hint-go' : undefined}>
                {walkHint || 'Click to look · W/S walk · A/D turn · Space jump · E talk'}
              </span>
            </div>
            <nav className="floor-directory" aria-label="Office floors">
              {FLOORS.map((floor) => (
                <button
                  key={floor.id}
                  type="button"
                  className="floor-chip"
                  onClick={() => {
                    window.location.hash = `#/floor/${floor.id}`
                  }}
                >
                  <span className="floor-chip-id">F{floor.id}</span>
                  <span className="floor-chip-name">{floor.name}</span>
                  <span className="floor-chip-wing">{floor.wing}</span>
                </button>
              ))}
            </nav>
            {vaultOpsOpen && (
              <div className="vault-board" aria-label="Desk vault board">
                <div className="vault-board-toolbar">
                  <span className="vault-ritual-hint">
                    ritual: make living-ritual / --discord · observe: make living-ritual-observe · paste draft from ritual draft row (never auto-posts)
                  </span>
                  <button
                    type="button"
                    className="vault-board-close"
                    onClick={() => setVaultOpsOpen(false)}
                  >
                    Close desk ops
                  </button>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">skips</span>
                  <span>
                    {(snap?.desk?.more?.skip_leaderboard?.top || [])
                      .slice(0, 5)
                      .map((s) => `${s.code}×${s.n}`)
                      .join(' · ') || 'quiet'}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">budgets</span>
                  <span>
                    {Object.entries(snap?.desk?.more?.tower_budgets || {})
                      .slice(0, 6)
                      .map(([id, n]) => `${id}:$${Number(n).toFixed(0)}`)
                      .join(' · ') || '—'}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">adapt</span>
                  <span>
                    {(() => {
                      const by = snap?.desk?.adapt?.by_bot || {}
                      let s = 0
                      let b = 0
                      for (const row of Object.values(by)) {
                        s += Number(row?.safe || 0)
                        b += Number(row?.big || 0)
                      }
                      return `safe×${s} · big×${b}`
                    })()}
                    {snap?.desk?.gate_a?.any_ready ? ' · Gate A ready' : ''}
                    {snap?.desk?.gate_b?.any_ready ? ' · Gate B ready' : ''}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">tip force</span>
                  <span
                    style={{
                      color: snap?.desk?.sports_tip?.active ? '#d4a017' : undefined,
                    }}
                  >
                    {snap?.desk?.sports_tip?.active
                      ? `tip-force T−${snap.desk.sports_tip.band} · ${snap.desk.sports_tip.force_sec || 45}s` +
                        (snap.desk.sports_tip.sample ? ` · ${snap.desk.sports_tip.sample}` : '')
                      : 'tip-force off · sports normal cadence'}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">tip feed</span>
                  <span
                    style={{
                      color: (() => {
                        const tr =
                          snap?.desk?.tip_radar ||
                          (snap?.desk?.master as { tip_radar?: { t5?: number } } | undefined)
                            ?.tip_radar
                        if (!tr) return undefined
                        return Number(tr.t5 || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const tr =
                        snap?.desk?.tip_radar ||
                        (snap?.desk?.master as {
                          tip_radar?: { label?: string; t5?: number; t15?: number; n?: number }
                        } | undefined)?.tip_radar
                      if (!tr) return 'tip radar pending'
                      return (
                        tr.label ||
                        `tip radar n=${tr.n ?? '—'} T-5=${tr.t5 ?? 0} T-15=${tr.t15 ?? 0}`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">empty</span>
                  <span
                    style={{
                      color: (() => {
                        const e =
                          snap?.desk?.empty_card ||
                          (snap?.desk?.master as { empty_card?: { pass?: boolean } } | undefined)
                            ?.empty_card
                        if (!e || e.pass == null) return undefined
                        return e.pass === false ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const e =
                        snap?.desk?.empty_card ||
                        (snap?.desk?.master as {
                          empty_card?: { label?: string; pass?: boolean; p50_s?: number }
                        } | undefined)?.empty_card
                      if (!e) return 'empty CARD pending'
                      return e.label || `empty CARD p50=${e.p50_s ?? '—'}s`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">near-miss</span>
                  <span
                    style={{
                      color: (() => {
                        const n =
                          snap?.desk?.near_miss ||
                          (snap?.desk?.master as {
                            near_miss?: { promote_ready?: boolean }
                          } | undefined)?.near_miss
                        if (!n) return undefined
                        return n.promote_ready ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const n =
                        snap?.desk?.near_miss ||
                        (snap?.desk?.master as {
                          near_miss?: {
                            label?: string
                            promote_ready?: boolean
                            auto_promote?: boolean
                          }
                        } | undefined)?.near_miss
                      if (!n) return 'near-miss pending'
                      return (
                        (n.label ||
                          `near-miss ready=${Boolean(n.promote_ready)}`) +
                        ' · auto_promote=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">skip-reg</span>
                  <span
                    style={{
                      color: (() => {
                        const s =
                          snap?.desk?.skip_regret ||
                          (snap?.desk?.master as {
                            skip_regret?: { green_twin?: boolean }
                          } | undefined)?.skip_regret
                        if (!s) return undefined
                        return s.green_twin ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const s =
                        snap?.desk?.skip_regret ||
                        (snap?.desk?.master as {
                          skip_regret?: {
                            label?: string
                            green_twin?: boolean
                            loosen_soft_gates?: boolean
                          }
                        } | undefined)?.skip_regret
                      if (!s) return 'skip-regret pending'
                      return (
                        (s.label || `skip-regret green_twin=${Boolean(s.green_twin)}`) +
                        ' · floors locked'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">hard-stop</span>
                  <span
                    style={{
                      color: (() => {
                        const h =
                          snap?.desk?.hard_stop ||
                          (snap?.desk?.master as {
                            hard_stop?: { promote_ready?: boolean }
                          } | undefined)?.hard_stop
                        if (!h) return undefined
                        return h.promote_ready ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const h =
                        snap?.desk?.hard_stop ||
                        (snap?.desk?.master as {
                          hard_stop?: {
                            label?: string
                            promote_ready?: boolean
                            auto_promote?: boolean
                            live?: boolean
                          }
                        } | undefined)?.hard_stop
                      if (!h) return 'hard-stop pending'
                      return (
                        (h.label ||
                          `hard-stop ready=${Boolean(h.promote_ready)}`) +
                        ' · auto_promote=False · live=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">injury</span>
                  <span
                    style={{
                      color: (() => {
                        const iw =
                          snap?.desk?.injury_wire ||
                          (snap?.desk?.master as {
                            injury_wire?: { n?: number; inbox_n?: number }
                          } | undefined)?.injury_wire
                        if (!iw) return undefined
                        return Number(iw.n || 0) + Number(iw.inbox_n || 0) > 0
                          ? '#d4a017'
                          : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const iw =
                        snap?.desk?.injury_wire ||
                        (snap?.desk?.master as {
                          injury_wire?: { label?: string; n?: number; inbox_n?: number }
                        } | undefined)?.injury_wire
                      if (!iw) return 'injury wire pending'
                      return iw.label || `injury wire n=${iw.n ?? 0} inbox=${iw.inbox_n ?? 0}`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">EIA</span>
                  <span
                    style={{
                      color: (() => {
                        const e =
                          snap?.desk?.eia_scout ||
                          (snap?.desk?.master as {
                            eia_scout?: { next_eta_hours?: number | null }
                          } | undefined)?.eia_scout
                        if (!e || e.next_eta_hours == null) return undefined
                        return Number(e.next_eta_hours) <= 24 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const e =
                        snap?.desk?.eia_scout ||
                        (snap?.desk?.master as {
                          eia_scout?: {
                            label?: string
                            n?: number
                            next_eta_hours?: number | null
                          }
                        } | undefined)?.eia_scout
                      if (!e) return 'EIA scout pending'
                      return (
                        e.label ||
                        `EIA scout n=${e.n ?? 0} next=${e.next_eta_hours ?? '—'}h`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">calendar</span>
                  <span
                    style={{
                      color: (() => {
                        const c =
                          snap?.desk?.calendar_scanner ||
                          (snap?.desk?.master as {
                            calendar_scanner?: { n?: number }
                          } | undefined)?.calendar_scanner
                        if (!c) return undefined
                        return Number(c.n || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const c =
                        snap?.desk?.calendar_scanner ||
                        (snap?.desk?.master as {
                          calendar_scanner?: { label?: string; n?: number }
                        } | undefined)?.calendar_scanner
                      if (!c) return 'calendar pending'
                      return c.label || `calendar events n=${c.n ?? 0}`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">blackout</span>
                  <span
                    style={{
                      color: (() => {
                        const b =
                          snap?.desk?.eia_blackout ||
                          (snap?.desk?.master as {
                            eia_blackout?: { blocked?: boolean }
                          } | undefined)?.eia_blackout
                        if (!b) return undefined
                        return b.blocked ? '#c45c26' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const b =
                        snap?.desk?.eia_blackout ||
                        (snap?.desk?.master as {
                          eia_blackout?: { label?: string; blocked?: boolean }
                        } | undefined)?.eia_blackout
                      if (!b) return 'EIA blackout pending'
                      return b.label || (b.blocked ? 'EIA blackout ACTIVE' : 'EIA blackout clear')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">pulse</span>
                  <span
                    style={{
                      color: (() => {
                        const p =
                          snap?.desk?.clerk_pulse ||
                          (snap?.desk?.master as {
                            clerk_pulse?: { stale?: boolean; soft_warn?: boolean }
                          } | undefined)?.clerk_pulse
                        if (!p) return undefined
                        if (p.stale) return '#c45c26'
                        if (p.soft_warn) return '#d4a017'
                        return undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const p =
                        snap?.desk?.clerk_pulse ||
                        (snap?.desk?.master as {
                          clerk_pulse?: { label?: string; stale?: boolean; soft_warn?: boolean }
                        } | undefined)?.clerk_pulse
                      if (!p) return 'clerk pulse pending'
                      return p.label || (p.stale ? 'pulse STALE' : p.soft_warn ? 'pulse WARN' : 'pulse ok')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">compact</span>
                  <span
                    style={{
                      color: (() => {
                        const c =
                          snap?.desk?.living_compact ||
                          (snap?.desk?.master as {
                            compact?: { ritual_ok?: boolean | null }
                          } | undefined)?.compact
                        if (!c || c.ritual_ok == null) return undefined
                        return c.ritual_ok ? undefined : '#d4a017'
                      })(),
                    }}
                  >
                    {(() => {
                      const c =
                        snap?.desk?.living_compact ||
                        (snap?.desk?.master as {
                          compact?: {
                            label?: string
                            ritual_label?: string
                            ritual_ok?: boolean | null
                            parts?: string[]
                          }
                        } | undefined)?.compact
                      if (!c) return 'living compact pending'
                      // Prefer full label (quiet → ritual → expand order from living_compact_card).
                      return c.label || 'living compact'
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">AI</span>
                  <span
                    style={{
                      color: (() => {
                        const ai =
                          snap?.desk?.living_ai ||
                          (snap?.desk?.master as { living_ai?: { raise_phi_n?: number } } | undefined)
                            ?.living_ai
                        if (!ai) return undefined
                        return Number(ai.raise_phi_n || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const ai =
                        snap?.desk?.living_ai ||
                        (snap?.desk?.master as {
                          living_ai?: { label?: string; raise_phi_n?: number }
                        } | undefined)?.living_ai
                      if (!ai) return 'living AI pending'
                      return (
                        ai.label ||
                        `raise_Φ=${ai.raise_phi_n ?? 0} · auto_write=False`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">quiet</span>
                  <span
                    style={{
                      color: (() => {
                        const q =
                          snap?.desk?.feature_quiet ||
                          (snap?.desk?.master as { feature_quiet?: { quiet?: boolean } } | undefined)
                            ?.feature_quiet
                        if (!q) return undefined
                        return q.quiet ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const q =
                        snap?.desk?.feature_quiet ||
                        (snap?.desk?.master as {
                          feature_quiet?: { label?: string; quiet?: boolean; alert?: string }
                        } | undefined)?.feature_quiet
                      if (!q) return 'feature quiet pending'
                      return q.label || q.alert || (q.quiet ? 'feature QUIET' : 'feature quiet ok')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">pager</span>
                  <span
                    style={{
                      color: (() => {
                        const p =
                          snap?.desk?.feature_quiet_pager ||
                          (snap?.desk?.master as {
                            feature_quiet_pager?: { page?: boolean }
                          } | undefined)?.feature_quiet_pager
                        if (!p) return undefined
                        return p.page ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const p =
                        snap?.desk?.feature_quiet_pager ||
                        (snap?.desk?.master as {
                          feature_quiet_pager?: {
                            label?: string
                            page?: boolean
                            auto_page?: boolean
                          }
                        } | undefined)?.feature_quiet_pager
                      if (!p) return 'feature quiet pager pending'
                      return (
                        (p.label || (p.page ? 'feature quiet PAGE' : 'feature quiet ok')) +
                        ' · auto_page=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">queue</span>
                  <span
                    style={{
                      color: (() => {
                        const q =
                          snap?.desk?.firm_queue ||
                          (snap?.desk?.master as {
                            firm_queue?: { deferred_n?: number; offers_n?: number }
                          } | undefined)?.firm_queue
                        if (!q) return undefined
                        return Number(q.deferred_n || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const q =
                        snap?.desk?.firm_queue ||
                        (snap?.desk?.master as {
                          firm_queue?: {
                            label?: string
                            offers_n?: number
                            deferred_n?: number
                            remaining_risk?: number | null
                          }
                        } | undefined)?.firm_queue
                      if (!q) return 'firm queue pending'
                      return (
                        q.label ||
                        `firm queue offers=${q.offers_n ?? '—'} def=${q.deferred_n ?? '—'} risk_left=${q.remaining_risk ?? '—'}`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">Gate A</span>
                  <span
                    style={{
                      color: (() => {
                        const g =
                          snap?.desk?.helper_gate_a ||
                          (snap?.desk?.master as {
                            helper_gate_a?: { ready_n?: number }
                          } | undefined)?.helper_gate_a
                        if (!g) return undefined
                        return Number(g.ready_n || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const g =
                        snap?.desk?.helper_gate_a ||
                        (snap?.desk?.master as {
                          helper_gate_a?: {
                            label?: string
                            ready_n?: number
                            helpers_n?: number
                            auto_promote?: boolean
                            places_orders?: boolean
                          }
                        } | undefined)?.helper_gate_a
                      if (!g) return 'helper Gate A pending'
                      return (
                        (g.label ||
                          `helper Gate A ready=${g.ready_n ?? 0}/${g.helpers_n ?? 0}`) +
                        ' · auto_promote=False · places=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">skips</span>
                  <span>
                    {(() => {
                      const s =
                        snap?.desk?.skip_taxonomy ||
                        (snap?.desk?.master as {
                          skip_taxonomy?: { label?: string; top_code?: string; top_n?: number }
                        } | undefined)?.skip_taxonomy
                      if (!s) return 'skip taxonomy pending'
                      return s.label || (s.top_code ? `top skip ${s.top_code} ×${s.top_n ?? 0}` : 'skip taxonomy quiet')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">distance</span>
                  <span
                    style={{
                      color: (() => {
                        const d =
                          snap?.desk?.distance_clerk ||
                          (snap?.desk?.master as {
                            distance_clerk?: { empty_card_pass?: boolean }
                          } | undefined)?.distance_clerk
                        if (!d || d.empty_card_pass == null) return undefined
                        return d.empty_card_pass === false ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const d =
                        snap?.desk?.distance_clerk ||
                        (snap?.desk?.master as {
                          distance_clerk?: { label?: string; empty_card_pass?: boolean }
                        } | undefined)?.distance_clerk
                      if (!d) return 'distance clerk pending'
                      return d.label || `distance empty_ok=${d.empty_card_pass ?? '—'}`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">quant</span>
                  <span
                    style={{
                      color: (() => {
                        const q =
                          snap?.desk?.quant_clerk ||
                          (snap?.desk?.master as {
                            quant_clerk?: { fit_pass?: boolean }
                          } | undefined)?.quant_clerk
                        if (!q || q.fit_pass == null) return undefined
                        return q.fit_pass === false ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const q =
                        snap?.desk?.quant_clerk ||
                        (snap?.desk?.master as {
                          quant_clerk?: {
                            label?: string
                            fit_pass?: boolean
                            fit_rate?: number | null
                            auto_write?: boolean
                          }
                        } | undefined)?.quant_clerk
                      if (!q) return 'quant clerk pending'
                      return (
                        (q.label || `quant fit_pass=${q.fit_pass ?? '—'} rate=${q.fit_rate ?? '—'}`) +
                        ' · auto_write=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">books</span>
                  <span
                    style={{
                      color: (() => {
                        const b =
                          snap?.desk?.bookkeeper ||
                          (snap?.desk?.master as {
                            bookkeeper?: { fee_ledger_complete?: boolean }
                          } | undefined)?.bookkeeper
                        if (!b || b.fee_ledger_complete == null) return undefined
                        return b.fee_ledger_complete === false ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const b =
                        snap?.desk?.bookkeeper ||
                        (snap?.desk?.master as {
                          bookkeeper?: { label?: string; fee_ledger_complete?: boolean }
                        } | undefined)?.bookkeeper
                      if (!b) return 'bookkeeper pending'
                      return b.label || `bookkeeper complete=${b.fee_ledger_complete ?? '—'}`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">report</span>
                  <span>
                    {(() => {
                      const r =
                        snap?.desk?.reporter ||
                        (snap?.desk?.master as {
                          reporter?: { label?: string; present?: boolean; auto_publish?: boolean }
                        } | undefined)?.reporter
                      if (!r) return 'reporter pending'
                      return (
                        (r.label || `reporter scorecard=${r.present ? 'yes' : 'no'}`) +
                        ' · auto_publish=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">sunday</span>
                  <span
                    style={{
                      color: (() => {
                        const s =
                          snap?.desk?.sunday_packet ||
                          (snap?.desk?.master as {
                            sunday_packet?: {
                              present?: boolean
                              ritual_ok?: boolean | null
                            }
                          } | undefined)?.sunday_packet
                        if (!s) return undefined
                        if (s.ritual_ok === false) return '#d4a017'
                        if (!s.present) return '#d4a017'
                        return undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const s =
                        snap?.desk?.sunday_packet ||
                        (snap?.desk?.master as {
                          sunday_packet?: {
                            label?: string
                            present?: boolean
                            ritual_ok?: boolean | null
                            auto_publish?: boolean
                          }
                        } | undefined)?.sunday_packet
                      if (!s) return 'sunday packet pending'
                      return (
                        (s.label || `sunday packet=${s.present ? 'yes' : 'no'}`) +
                        (s.ritual_ok == null ? '' : ` · ritual_ok=${Boolean(s.ritual_ok)}`) +
                        ' · auto_publish=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">empty bee</span>
                  <span
                    style={{
                      color: (() => {
                        const e =
                          snap?.desk?.empty_card_bee ||
                          (snap?.desk?.master as {
                            empty_card_bee?: { breaches?: number }
                          } | undefined)?.empty_card_bee
                        if (!e) return undefined
                        return Number(e.breaches || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const e =
                        snap?.desk?.empty_card_bee ||
                        (snap?.desk?.master as {
                          empty_card_bee?: { label?: string; breaches?: number; n?: number }
                        } | undefined)?.empty_card_bee
                      if (!e) return 'empty bee pending'
                      return e.label || `empty bee n=${e.n ?? 0} breaches=${e.breaches ?? 0}`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">nm clerk</span>
                  <span
                    style={{
                      color: (() => {
                        const n =
                          snap?.desk?.near_miss_clerk ||
                          (snap?.desk?.master as {
                            near_miss_clerk?: { promote_ready?: boolean }
                          } | undefined)?.near_miss_clerk
                        if (!n) return undefined
                        return n.promote_ready ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const n =
                        snap?.desk?.near_miss_clerk ||
                        (snap?.desk?.master as {
                          near_miss_clerk?: {
                            label?: string
                            promote_ready?: boolean
                            auto_promote?: boolean
                          }
                        } | undefined)?.near_miss_clerk
                      if (!n) return 'near-miss clerk pending'
                      return (
                        (n.label || `near-miss clerk ready=${Boolean(n.promote_ready)}`) +
                        ' · auto_promote=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">hs clerk</span>
                  <span
                    style={{
                      color: (() => {
                        const h =
                          snap?.desk?.hard_stop_clerk ||
                          (snap?.desk?.master as {
                            hard_stop_clerk?: { promote_ready?: boolean }
                          } | undefined)?.hard_stop_clerk
                        if (!h) return undefined
                        return h.promote_ready ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const h =
                        snap?.desk?.hard_stop_clerk ||
                        (snap?.desk?.master as {
                          hard_stop_clerk?: {
                            label?: string
                            promote_ready?: boolean
                            auto_promote?: boolean
                            live?: boolean
                          }
                        } | undefined)?.hard_stop_clerk
                      if (!h) return 'hard-stop clerk pending'
                      return (
                        (h.label || `hard-stop clerk ready=${Boolean(h.promote_ready)}`) +
                        ' · auto_promote=False · live=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">bleed clk</span>
                  <span
                    style={{
                      color: (() => {
                        const b =
                          snap?.desk?.bleed_clerk ||
                          (snap?.desk?.master as {
                            bleed_clerk?: { bleed_pass?: boolean }
                          } | undefined)?.bleed_clerk
                        if (!b || b.bleed_pass == null) return undefined
                        return b.bleed_pass === false ? '#c45c26' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const b =
                        snap?.desk?.bleed_clerk ||
                        (snap?.desk?.master as {
                          bleed_clerk?: {
                            label?: string
                            bleed_pass?: boolean
                            bleed_ratio?: number | null
                          }
                        } | undefined)?.bleed_clerk
                      if (!b) return 'bleed clerk pending'
                      return (
                        b.label ||
                        `bleed clerk ratio=${b.bleed_ratio ?? '—'} pass=${b.bleed_pass ?? '—'}`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">skip-twin</span>
                  <span
                    style={{
                      color: (() => {
                        const s =
                          snap?.desk?.skip_twin_clerk ||
                          (snap?.desk?.master as {
                            skip_twin_clerk?: { promote_ready?: boolean }
                          } | undefined)?.skip_twin_clerk
                        if (!s) return undefined
                        return s.promote_ready ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const s =
                        snap?.desk?.skip_twin_clerk ||
                        (snap?.desk?.master as {
                          skip_twin_clerk?: {
                            label?: string
                            promote_ready?: boolean
                            auto_promote?: boolean
                          }
                        } | undefined)?.skip_twin_clerk
                      if (!s) return 'skip-twin clerk pending'
                      return (
                        (s.label || `skip-twin ready=${Boolean(s.promote_ready)}`) +
                        ' · auto_promote=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">CLV close</span>
                  <span
                    style={{
                      color: (() => {
                        const c =
                          snap?.desk?.clv_closer ||
                          (snap?.desk?.master as { clv_closer?: { pass?: boolean } } | undefined)
                            ?.clv_closer
                        if (!c || c.pass == null) return undefined
                        return c.pass === false ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const c =
                        snap?.desk?.clv_closer ||
                        (snap?.desk?.master as {
                          clv_closer?: { label?: string; pass?: boolean; complete?: number; n?: number }
                        } | undefined)?.clv_closer
                      if (!c) return 'CLV closer pending'
                      return (
                        c.label ||
                        `CLV closer n=${c.n ?? '—'} complete=${c.complete ?? '—'} ${
                          c.pass === false ? 'gaps' : 'ok'
                        }`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">t-digest</span>
                  <span
                    style={{
                      color: (() => {
                        const t =
                          snap?.desk?.timer_digest ||
                          (snap?.desk?.master as {
                            timer_digest?: { alive?: boolean; status?: string }
                          } | undefined)?.timer_digest
                        if (!t) return undefined
                        if (t.alive === false || t.status === 'dead') return '#c45c26'
                        return undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const t =
                        snap?.desk?.timer_digest ||
                        (snap?.desk?.master as {
                          timer_digest?: { label?: string; alive?: boolean; status?: string }
                        } | undefined)?.timer_digest
                      if (!t) return 'timer digest pending'
                      return t.label || `timer digest ${t.status || (t.alive === false ? 'dead' : 'alive')}`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">digests</span>
                  <span
                    style={{
                      color: (() => {
                        const inv =
                          snap?.desk?.digest_inventory ||
                          (snap?.desk?.master as {
                            digest_inventory?: { pass?: boolean }
                          } | undefined)?.digest_inventory
                        if (!inv) return undefined
                        return inv.pass === false ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const inv =
                        snap?.desk?.digest_inventory ||
                        (snap?.desk?.master as {
                          digest_inventory?: { label?: string; pass?: boolean }
                        } | undefined)?.digest_inventory
                      if (!inv) return 'digest inventory pending'
                      return inv.label || (inv.pass === false ? 'digests thin' : 'digests ok')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">swarm</span>
                  <span
                    style={{
                      color: (() => {
                        const sw =
                          snap?.desk?.swarm_lights || snap?.desk?.master?.swarm_lights
                        if (!sw || sw.error) return undefined
                        if (sw.pass || sw.color === 'green') return '#6fbf73'
                        if (sw.color === 'amber' || sw.pass === false) return '#d4a017'
                        return undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const sw =
                        snap?.desk?.swarm_lights || snap?.desk?.master?.swarm_lights
                      if (!sw || sw.error) return 'insight swarm pending'
                      const mark = sw.pass ? '●' : '◐'
                      return (
                        `${mark} ${sw.label || `insight ${sw.insight_n}:${sw.betting_n}`}` +
                        (sw.color ? ` · ${sw.color}` : '')
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">hill</span>
                  <span
                    style={{
                      color: (() => {
                        const h =
                          snap?.desk?.hillclimb_chip ||
                          (snap?.desk?.master as {
                            hillclimb_chip?: { active_name?: string | null }
                          } | undefined)?.hillclimb_chip
                        if (!h) return undefined
                        return h.active_name ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const h =
                        snap?.desk?.hillclimb_chip ||
                        (snap?.desk?.master as {
                          hillclimb_chip?: { label?: string; active_name?: string | null }
                        } | undefined)?.hillclimb_chip
                      if (!h) return 'hillclimb pending'
                      return h.label || (h.active_name ? `lever=${h.active_name}` : 'hillclimb none')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">gaps</span>
                  <span
                    style={{
                      color: (() => {
                        const g =
                          snap?.desk?.dual_control_gaps ||
                          (snap?.desk?.master as {
                            dual_control_gaps?: { page?: boolean; gaps_n?: number }
                          } | undefined)?.dual_control_gaps
                        if (!g) return undefined
                        return g.page || Number(g.gaps_n || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const g =
                        snap?.desk?.dual_control_gaps ||
                        (snap?.desk?.master as {
                          dual_control_gaps?: { label?: string; page?: boolean; gaps_n?: number }
                        } | undefined)?.dual_control_gaps
                      if (!g) return 'dual gaps pending'
                      return g.label || (g.page ? 'dual-control gaps' : 'dual gaps clear')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">fills</span>
                  <span
                    style={{
                      color: (() => {
                        const c =
                          snap?.desk?.completions || snap?.desk?.master?.completions
                        if (!c || c.error) return undefined
                        const n = Number(c.eligible_completions_today ?? 0)
                        // Observe thin: no eligible completions yet today.
                        return n === 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const c =
                        snap?.desk?.completions || snap?.desk?.master?.completions
                      if (!c || c.error) return 'completions pending'
                      const n = c.eligible_completions_today
                      const pnl = c.eligible_pnl_today
                      return (
                        `eligible today ${n ?? '—'}` +
                        (pnl != null ? ` · pnl ${Number(pnl).toFixed(2)}` : '')
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">green</span>
                  <span
                    style={{
                      color: (() => {
                        const g =
                          snap?.desk?.green_day ||
                          (snap?.desk?.master as {
                            green_day?: { red_n?: number; all_fee_clear_green?: boolean }
                          } | undefined)?.green_day
                        if (!g) return undefined
                        if (g.all_fee_clear_green) return '#6fbf73'
                        if (Number(g.red_n || 0) > 0) return '#c45c26'
                        return undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const g =
                        snap?.desk?.green_day ||
                        (snap?.desk?.master as {
                          green_day?: { label?: string; green_n?: number; red_n?: number }
                        } | undefined)?.green_day
                      if (!g) return 'green-day pending'
                      return (
                        g.label ||
                        `green=${g.green_n ?? '—'} red=${g.red_n ?? '—'}`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">bleed</span>
                  <span
                    style={{
                      color: (() => {
                        const b =
                          snap?.desk?.bleed ||
                          (snap?.desk?.master as { bleed?: { pass?: boolean } } | undefined)
                            ?.bleed
                        if (!b || b.pass == null) return undefined
                        return b.pass === false ? '#c45c26' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const b =
                        snap?.desk?.bleed ||
                        (snap?.desk?.master as {
                          bleed?: { label?: string; pass?: boolean; ratio?: number | null }
                        } | undefined)?.bleed
                      if (!b) return 'bleed pending'
                      return b.label || `bleed ratio=${b.ratio ?? '—'} ${b.pass === false ? 'hot' : 'ok'}`
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">CLV</span>
                  <span
                    style={{
                      color: (() => {
                        const c =
                          snap?.desk?.clv ||
                          (snap?.desk?.master as { clv?: { pass?: boolean } } | undefined)?.clv
                        if (!c || c.pass == null) return undefined
                        return c.pass === false ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const c =
                        snap?.desk?.clv ||
                        (snap?.desk?.master as {
                          clv?: { label?: string; pass?: boolean; complete?: number; n?: number }
                        } | undefined)?.clv
                      if (!c) return 'CLV pending'
                      return (
                        c.label ||
                        `CLV complete=${c.complete ?? '—'}/${c.n ?? '—'} ${
                          c.pass === false ? 'gaps' : 'ok'
                        }`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">calib</span>
                  <span
                    style={{
                      color: (() => {
                        const c =
                          snap?.desk?.calib_nag ||
                          (snap?.desk?.master as { calib_nag?: { tickets_n?: number } } | undefined)
                            ?.calib_nag
                        if (!c) return undefined
                        return Number(c.tickets_n || 0) > 0 ? '#d4a017' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const c =
                        snap?.desk?.calib_nag ||
                        (snap?.desk?.master as {
                          calib_nag?: { label?: string; tickets_n?: number; auto_write_phi?: boolean }
                        } | undefined)?.calib_nag
                      if (!c) return 'calib nag pending'
                      return (
                        c.label ||
                        `calib raise_Φ=${c.tickets_n ?? 0} · auto_write=${c.auto_write_phi === true}`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">timer</span>
                  <span
                    style={{
                      color: (() => {
                        const t =
                          snap?.desk?.timer_heartbeat ||
                          (snap?.desk?.master as {
                            timer_heartbeat?: { alive?: boolean }
                          } | undefined)?.timer_heartbeat
                        if (!t || t.alive == null) return undefined
                        return t.alive === false ? '#c45c26' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const t =
                        snap?.desk?.timer_heartbeat ||
                        (snap?.desk?.master as {
                          timer_heartbeat?: { label?: string; alive?: boolean; age_sec?: number }
                        } | undefined)?.timer_heartbeat
                      if (!t) return 'timer heartbeat pending'
                      return (
                        t.label ||
                        `timer ${t.alive === false ? 'DEAD' : 'alive'}` +
                          (t.age_sec != null ? ` age=${t.age_sec}s` : '')
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">teller</span>
                  <span>
                    {snap?.desk?.living_memory_line ||
                      snap?.desk?.teller_living?.memory_line ||
                      snap?.desk?.teller_memory?.recent?.[0]?.text ||
                      'living teller pending'}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">floors</span>
                  <span
                    style={{
                      color: (() => {
                        const f =
                          snap?.desk?.fee_floors_assert ||
                          (snap?.desk?.master as { fee_floors_assert?: { all_ok?: boolean } } | undefined)
                            ?.fee_floors_assert
                        if (!f) return undefined
                        return f.all_ok === false ? '#c45c26' : '#6fbf73'
                      })(),
                    }}
                  >
                    {(() => {
                      const f =
                        snap?.desk?.fee_floors_assert ||
                        (snap?.desk?.master as { fee_floors_assert?: { label?: string; all_ok?: boolean } } | undefined)
                          ?.fee_floors_assert
                      if (!f) return 'fee floors pending'
                      return f.label || (f.all_ok ? 'floors locked ok' : 'floors CHECK')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">dual</span>
                  <span
                    style={{
                      color: (() => {
                        const d =
                          snap?.desk?.dual_control_chip ||
                          (snap?.desk?.master as {
                            dual_control_chip?: { checklist_complete?: boolean; arm_ready_paper?: boolean }
                          } | undefined)?.dual_control_chip
                        if (!d) return undefined
                        if (d.arm_ready_paper) return '#6fbf73'
                        if (d.checklist_complete === false) return '#d4a017'
                        return undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const d =
                        snap?.desk?.dual_control_chip ||
                        (snap?.desk?.master as {
                          dual_control_chip?: {
                            label?: string
                            signed_n?: number
                            items_n?: number
                            live_orders_enabled?: boolean
                          }
                        } | undefined)?.dual_control_chip
                      if (!d) return 'dual-control pending'
                      return (
                        (d.label ||
                          `dual-control signed=${d.signed_n ?? '—'}/${d.items_n ?? '—'}`) +
                        ' · live=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">ruin</span>
                  <span
                    style={{
                      color: (() => {
                        const r =
                          snap?.desk?.ruin_drill_chip ||
                          (snap?.desk?.master as {
                            ruin_drill_chip?: { active?: boolean; practiced_this_month?: boolean }
                          } | undefined)?.ruin_drill_chip
                        if (!r) return undefined
                        if (r.active) return '#c45c26'
                        if (r.practiced_this_month === false) return '#d4a017'
                        return undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const r =
                        snap?.desk?.ruin_drill_chip ||
                        (snap?.desk?.master as {
                          ruin_drill_chip?: {
                            label?: string
                            active?: boolean
                            practiced_this_month?: boolean
                            level?: string
                          }
                        } | undefined)?.ruin_drill_chip
                      if (!r) return 'ruin drill pending'
                      return (
                        r.label ||
                        `ruin drill active=${Boolean(r.active)} practiced_month=${Boolean(r.practiced_this_month)}`
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">expand</span>
                  <span
                    style={{
                      color: (() => {
                        const g =
                          snap?.desk?.betting_expand_gate ||
                          (snap?.desk?.master as { betting_expand_gate?: { blocked?: boolean } } | undefined)
                            ?.betting_expand_gate
                        if (!g) return undefined
                        return g.blocked ? '#c45c26' : '#6fbf73'
                      })(),
                    }}
                  >
                    {(() => {
                      const g =
                        snap?.desk?.betting_expand_gate ||
                        (snap?.desk?.master as {
                          betting_expand_gate?: {
                            label?: string
                            blocked?: boolean
                            soft_copy?: string
                            reason?: string
                          }
                        } | undefined)?.betting_expand_gate
                      if (!g) return 'expand gate pending'
                      if (g.blocked) {
                        return g.soft_copy || g.reason || g.label || 'betting expand BLOCKED'
                      }
                      return g.label || 'expand ok (paper)'
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">doctor</span>
                  <span
                    style={{
                      color: (() => {
                        const d =
                          snap?.desk?.living_doctor ||
                          (snap?.desk?.master as { living_doctor?: { ok?: boolean } } | undefined)
                            ?.living_doctor
                        if (!d) return undefined
                        return d.ok ? '#6fbf73' : '#c45c26'
                      })(),
                    }}
                  >
                    {(() => {
                      const d =
                        snap?.desk?.living_doctor ||
                        (snap?.desk?.master as { living_doctor?: { label?: string; ok?: boolean } } | undefined)
                          ?.living_doctor
                      if (!d) return 'living doctor pending'
                      return d.label || (d.ok ? 'doctor OK' : 'doctor FAIL')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">doc age</span>
                  <span
                    style={{
                      color: (() => {
                        const a =
                          snap?.desk?.doctor_age ||
                          (snap?.desk?.master as { doctor_age?: { stale?: boolean } } | undefined)
                            ?.doctor_age
                        if (!a) return undefined
                        return a.stale ? '#c45c26' : undefined
                      })(),
                    }}
                  >
                    {(() => {
                      const a =
                        snap?.desk?.doctor_age ||
                        (snap?.desk?.master as {
                          doctor_age?: { label?: string; stale?: boolean }
                        } | undefined)?.doctor_age
                      if (!a) return 'doctor age pending'
                      return a.label || (a.stale ? 'doctor stale' : 'doctor age ok')
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">ritual</span>
                  <span
                    style={{
                      color: (() => {
                        const r =
                          snap?.desk?.ritual_observe ||
                          (snap?.desk?.master as {
                            ritual_observe?: { ritual_ok?: boolean; exit_ok?: boolean }
                          } | undefined)?.ritual_observe
                        if (!r) return undefined
                        if (r.ritual_ok) return '#6fbf73'
                        if (r.exit_ok === false) return '#c45c26'
                        return '#d4a017'
                      })(),
                    }}
                  >
                    {(() => {
                      const r =
                        snap?.desk?.ritual_observe ||
                        (snap?.desk?.master as {
                          ritual_observe?: {
                            label?: string
                            ritual_ok?: boolean
                            exit_ok?: boolean
                            auto_publish?: boolean
                          }
                        } | undefined)?.ritual_observe
                      if (!r) return 'ritual observe pending'
                      return (
                        (r.label ||
                          `ritual_ok=${Boolean(r.ritual_ok)} exit_ok=${Boolean(r.exit_ok)}`) +
                        ' · auto_publish=False'
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">ritual draft</span>
                  <span className="vault-ritual-draft">
                    {(() => {
                      const copy =
                        snap?.desk?.ritual_soft_copy ||
                        snap?.desk?.ritual_discord ||
                        (snap?.desk?.master as {
                          ritual_soft_copy?: string
                          ritual_discord?: string
                        } | undefined)?.ritual_soft_copy ||
                        (snap?.desk?.master as {
                          ritual_discord?: string
                        } | undefined)?.ritual_discord
                      if (!copy) {
                        return 'make living-ritual-discord · staff paste only · never auto-posts'
                      }
                      const one = String(copy).split('\n').filter(Boolean).slice(0, 2).join(' · ')
                      return one.length > 160 ? `${one.slice(0, 157)}…` : one
                    })()}
                  </span>
                </div>
                <div className="vault-board-row">
                  <span className="vb-label">bleed</span>
                  <span>
                    {(() => {
                      const sb = snap?.desk?.master?.stopbleed
                      if (!sb) return 'memecoin measure pending'
                      return (
                        `stop×${sb.stop_exits ?? 0} · flip×${sb.model_flip_exits ?? 0}` +
                        (sb.red_day_locked ? ' · RED LOCK' : '') +
                        (sb.expand_volume ? ' · volume ok' : ' · no volume expand')
                      )
                    })()}
                  </span>
                </div>
                <div className="vault-board-row tax-edu">
                  <span className="vb-label">fill tax</span>
                  <span>
                    +{(((snap?.desk?.ops?.fill_tax ?? snap?.desk?.gate_a?.fill_tax) ?? 0.01) * 100).toFixed(0)}¢
                    adverse on boards — untaxed paper wins are not live-ready
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {view === 'city' && (
          <>
            <TowerRail
              bots={bots}
              onSelect={(id) => {
                openTower(id)
              }}
            />
            <div className="day-strip" aria-hidden={false}>
              <span>{snap?.desk?.central_check || 'Central clock pending'}</span>
              <span>{snap?.desk?.status_line || ''}</span>
            </div>
          </>
        )}
      </div>

      <Ticker bots={bots} botId={view === 'office' ? selectedId : null} />
    </div>
  )
}
