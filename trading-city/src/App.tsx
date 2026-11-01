import { Canvas } from '@react-three/fiber'
import { Suspense, useMemo, useState } from 'react'
import { useSnapshot } from './data/useSnapshot'
import { Banners } from './hud/Banners'
import { CityHologramLayer } from './hud/Holograms'
import { Monitors } from './hud/Monitors'
import { Ticker } from './hud/Ticker'
import { CityScene } from './scene/CityScene'
import { OfficeScene } from './scene/OfficeScene'
import type { BotRow } from './types'

export default function App() {
  const { snap, mode, error, loading, updatedAt } = useSnapshot()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const bots = snap?.bots || []
  const selected: BotRow | null = useMemo(
    () => bots.find((b) => b.id === selectedId) || null,
    [bots, selectedId],
  )
  const office = Boolean(selected)

  return (
    <div className={`app ${office ? 'office' : 'city'}`}>
      <div className="stage">
        <Canvas
          dpr={[1, 1.75]}
          gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
          camera={{ position: [0, 12, 14], fov: 46 }}
        >
          <Suspense fallback={null}>
            {office && selected ? (
              <OfficeScene bot={selected} />
            ) : (
              <CityScene bots={bots} selectedId={selectedId} onSelect={setSelectedId} />
            )}
          </Suspense>
        </Canvas>

        <header className="chrome-top">
          <div className="brand-block">
            <h1 className="brand">PIMP-CITY</h1>
            <p className="tagline">Neon paper desk · five towers · live snapshot</p>
          </div>
          <div className="chrome-actions">
            {office ? (
              <button type="button" className="back-btn" onClick={() => setSelectedId(null)}>
                ← Back to city
              </button>
            ) : (
              <a className="back-btn ghost" href="/pimp-trading">
                PIMP-TRADING
              </a>
            )}
            <span className="meta">
              {loading && !snap ? 'loading…' : mode === 'live' ? 'live desk' : 'offline demo'}
              {updatedAt ? ` · ${new Date(updatedAt).toLocaleTimeString()}` : ''}
            </span>
          </div>
        </header>

        <Banners
          mode={mode}
          paperBanner={snap?.banner}
          error={error}
          roi={snap?.roi_system}
        />

        {!office && (
          <CityHologramLayer bots={bots} desk={snap?.desk} onSelect={setSelectedId} />
        )}

        {office && selected && (
          <div className="office-hud">
            <div className="office-title">
              <strong>{selected.name}</strong>
              <span>{selected.id}</span>
            </div>
            <Monitors bot={selected} desk={snap?.desk} />
          </div>
        )}

        {!office && (
          <div className="day-strip" aria-hidden={false}>
            <span>{snap?.desk?.central_check || 'Central clock pending'}</span>
            <span>{snap?.desk?.status_line || ''}</span>
          </div>
        )}
      </div>

      <Ticker bots={bots} botId={office ? selectedId : null} />
    </div>
  )
}
