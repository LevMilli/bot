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

export default function App() {
  const { snap, mode, error, loading, updatedAt, connectLive } = useSnapshot()
  const [view, setView] = useState<View>('city')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [fromBank, setFromBank] = useState(false)
  const [screensOpen, setScreensOpen] = useState(false)

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

  const backToCity = () => {
    setSelectedId(null)
    setFromBank(false)
    setView('city')
  }

  const backToBank = () => {
    setSelectedId(null)
    setFromBank(true)
    setView('bank')
  }

  return (
    <div className={`app ${view !== 'city' ? 'office' : 'city'}`}>
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
              <BankScene bots={bots} desk={snap?.desk} onSelectTeller={openTeller} />
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
              {view === 'bank'
                ? 'Neon paper trust · square tellers · desk board'
                : view === 'office' && fromBank
                  ? 'Teller desk · paper trades · switch windows'
                  : 'Neon paper desk · five towers · live snapshot'}
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
            ) : (
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
