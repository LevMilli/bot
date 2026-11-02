import { AdaptiveDpr, AdaptiveEvents } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Suspense, useEffect, useMemo, useState } from 'react'
import { useSnapshot } from './data/useSnapshot'
import { Banners } from './hud/Banners'
import { Monitors } from './hud/Monitors'
import { Ticker } from './hud/Ticker'
import { TowerRail } from './hud/TowerRail'
import { beamColorFor } from './data/format'
import { CityScene } from './scene/CityScene'
import { OfficeScene } from './scene/OfficeScene'
import { BankScene } from './scene/BankScene'
import type { BotRow } from './types'

type View = 'city' | 'bank' | 'office'

function guestModeFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get('guest') === '1'
  } catch {
    return false
  }
}

export default function App() {
  const { snap, mode, error, loading, updatedAt, connectLive } = useSnapshot()
  const [view, setView] = useState<View>('city')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [fromBank, setFromBank] = useState(false)
  const [screensOpen, setScreensOpen] = useState(false)
  /** Desk ops HUD (skips / budgets / adapt / fill tax) — opens from ledger/compliance click. */
  const [vaultOpsOpen, setVaultOpsOpen] = useState(false)
  const guest = useMemo(() => guestModeFromUrl(), [])

  const bots = snap?.bots || []
  const selected: BotRow | null = useMemo(
    () => bots.find((b) => b.id === selectedId) || null,
    [bots, selectedId],
  )

  const openVault = () => {
    setSelectedId(null)
    setFromBank(true)
    setView('bank')
  }

  const openTeller = (id: string) => {
    setSelectedId(id)
    setFromBank(true)
    setView('office')
  }

  const openTower = (id: string) => {
    setSelectedId(id)
    setFromBank(false)
    setView('office')
  }

  useEffect(() => {
    setScreensOpen(false)
  }, [selectedId, view])

  useEffect(() => {
    if (view !== 'bank') setVaultOpsOpen(false)
  }, [view])

  const backToCity = () => {
    setSelectedId(null)
    setFromBank(false)
    setVaultOpsOpen(false)
    setView('city')
  }

  const backToBank = () => {
    setSelectedId(null)
    setFromBank(true)
    setView('bank')
  }

  return (
    <div className={`app ${view !== 'city' ? 'office' : 'city'}${guest ? ' guest' : ''}`}>
      <div className="stage">
        <Canvas
          dpr={[1, 1]}
          gl={{ antialias: false, alpha: false, powerPreference: 'high-performance' }}
          camera={{ position: [0, 12, 14], fov: 46 }}
          performance={{ min: 0.4 }}
        >
          <AdaptiveDpr pixelated />
          <AdaptiveEvents />
          <Suspense fallback={null}>
            {view === 'office' && selected ? (
              <OfficeScene
                bot={selected}
                bots={bots}
                desk={snap?.desk}
                onOpenScreens={() => setScreensOpen(true)}
              />
            ) : view === 'bank' ? (
              <BankScene
                bots={bots}
                desk={snap?.desk}
                onSelectTeller={openTeller}
                onOpenDeskOps={() => setVaultOpsOpen(true)}
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
            {view === 'office' && fromBank ? (
              <button type="button" className="back-btn" onClick={backToBank}>
                ← Back to bank
              </button>
            ) : view !== 'city' ? (
              <button type="button" className="back-btn" onClick={backToCity}>
                ← Back to city
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
            <div className="office-title">
              <strong>{fromBank ? `Teller · ${selected.name}` : selected.name}</strong>
              <span>{selected.id}</span>
              <span className="screen-hint">click a screen for the trades</span>
            </div>
            {fromBank && (
              <div className="teller-switch" role="tablist" aria-label="Switch teller">
                {bots.map((bot, i) => (
                  <button
                    key={bot.id}
                    type="button"
                    role="tab"
                    aria-selected={bot.id === selected.id}
                    className={`teller-chip ${bot.id === selected.id ? 'active' : ''}`}
                    style={{ borderColor: beamColorFor(bot.id, i) }}
                    onClick={() => openTeller(bot.id)}
                  >
                    {bot.name}
                  </button>
                ))}
              </div>
            )}
          </div>
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
              <span>A/D · ←→ snap · W/S · ↑↓ zoom free · Enter open · drag to look</span>
            </div>
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
            <TowerRail bots={bots} onSelect={openTower} />
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
