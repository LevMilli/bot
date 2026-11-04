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
                  <span className="vb-label">tip</span>
                  <span>
                    {snap?.desk?.sports_tip?.active
                      ? `T−${snap.desk.sports_tip.band} force ${snap.desk.sports_tip.force_sec || 45}s` +
                        (snap.desk.sports_tip.sample ? ` · ${snap.desk.sports_tip.sample}` : '')
                      : 'no tip-force · sports on normal cadence'}
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
