import { useMemo, useRef } from 'react'
import { Html, PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow, Desk } from '../types'
import { BEAM_COLORS, money, pnlTone, workersOnShift } from '../data/format'
import { botPose } from '../data/botPose'
import { vaultBoardTexture } from '../hud/monitorTextures'
import { NeonBloom } from './Effects'
import { BotFigure } from './BotFigure'

type Props = {
  bots: BotRow[]
  desk?: Desk
  onSelectTeller: (id: string) => void
}

const MARBLE = '#e8e0d0'
const BRASS = '#c9a227'
const INK = '#12161e'

function TellerStation({
  bot,
  index,
  x,
  onSelect,
}: {
  bot: BotRow | null
  index: number
  x: number
  onSelect: (id: string) => void
}) {
  const color = BEAM_COLORS[index % BEAM_COLORS.length]
  const offline = !bot || bot.present === false
  const pose = bot ? botPose(bot) : 'waiting'

  return (
    <group position={[x, 0, -0.2]}>
      {/* counter */}
      <mesh position={[0, 0.95, 0.35]} castShadow>
        <boxGeometry args={[1.55, 0.12, 0.85]} />
        <meshStandardMaterial color={MARBLE} roughness={0.35} metalness={0.15} />
      </mesh>
      <mesh position={[0, 0.95, 0.78]}>
        <boxGeometry args={[1.55, 0.04, 0.06]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.28} emissive={BRASS} emissiveIntensity={0.15} />
      </mesh>
      <mesh position={[0, 0.48, 0.15]}>
        <boxGeometry args={[1.45, 0.85, 0.5]} />
        <meshStandardMaterial color="#2a2438" roughness={0.7} />
      </mesh>
      {/* glass partition */}
      <mesh position={[0, 1.55, 0.05]}>
        <boxGeometry args={[1.5, 1.05, 0.04]} />
        <meshStandardMaterial color="#7ef9ff" transparent opacity={0.12} metalness={0.2} roughness={0.1} />
      </mesh>
      <mesh position={[0, 2.1, 0.05]}>
        <boxGeometry args={[1.55, 0.06, 0.08]} />
        <meshStandardMaterial color={BRASS} metalness={0.75} roughness={0.3} />
      </mesh>
      {/* name plate */}
      <mesh
        position={[0, 1.55, 0.4]}
        onClick={(e) => {
          e.stopPropagation()
          if (bot) onSelect(bot.id)
        }}
        onPointerOver={() => {
          if (bot) document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[1.2, 0.28, 0.04]} />
        <meshStandardMaterial color={INK} emissive={color} emissiveIntensity={0.35} />
      </mesh>
      <Html position={[0, 1.55, 0.44]} center distanceFactor={8} style={{ pointerEvents: 'none' }}>
        <div
          style={{
            fontFamily: 'IBM Plex Mono, monospace',
            fontSize: '11px',
            color: '#f4f7ff',
            textAlign: 'center',
            whiteSpace: 'nowrap',
            textShadow: '0 0 8px #000',
          }}
        >
          <strong>{bot?.name || `Teller ${index + 1}`}</strong>
          <div style={{ opacity: 0.75, fontSize: '10px' }}>{offline ? 'offline' : bot?.id}</div>
          {!offline && bot && (
            <div
              style={{
                opacity: 0.9,
                fontSize: '10px',
                color: bot.starved ? '#ff6b6b' : '#9ef0c4',
              }}
            >
              EV {bot.expectancy == null ? '—' : money(bot.expectancy, true)}
              {bot.starved ? ' · starve' : ''}
              {bot.shadow?.active ? ' · SHADOW' : ''}
            </div>
          )}
        </div>
      </Html>
      {/* teller bot */}
      <group position={[0, 0.05, -0.35]} scale={0.92}>
        <BotFigure pose={pose} />
      </group>
      {/* clickable pad in front of counter */}
      <mesh
        position={[0, 0.02, 1.05]}
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={(e) => {
          e.stopPropagation()
          if (bot) onSelect(bot.id)
        }}
        onPointerOver={() => {
          if (bot) document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <circleGeometry args={[0.55, 24]} />
        <meshBasicMaterial color={color} transparent opacity={0.22} />
      </mesh>
    </group>
  )
}

function ProfitBoard({ desk }: { desk?: Desk }) {
  const map = useMemo(() => vaultBoardTexture(desk), [desk])
  useFrame(() => {
    map.needsUpdate = true
  })
  return (
    <group position={[0, 3.35, -2.85]}>
      <mesh>
        <boxGeometry args={[7.2, 1.35, 0.12]} />
        <meshStandardMaterial color="#0a0e16" metalness={0.4} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0, 0.07]}>
        <planeGeometry args={[6.8, 1.15]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.72, 0.04]}>
        <boxGeometry args={[7.3, 0.06, 0.08]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
    </group>
  )
}

/** Interior APEX-CITY bank — five teller windows + net-profit board. */
export function BankScene({ bots, desk, onSelectTeller }: Props) {
  const cam = useRef<Cam>(null)
  const tellers = useMemo(() => {
    const list: (BotRow | null)[] = [...bots]
    while (list.length < 5) list.push(null)
    return list.slice(0, 5)
  }, [bots])
  const workers = workersOnShift(bots)

  useFrame((_, dt) => {
    if (!cam.current) return
    const target = { x: 0, y: 2.55, z: 5.6 }
    cam.current.position.x += (target.x - cam.current.position.x) * Math.min(1, dt * 2.2)
    cam.current.position.y += (target.y - cam.current.position.y) * Math.min(1, dt * 2.2)
    cam.current.position.z += (target.z - cam.current.position.z) * Math.min(1, dt * 2.2)
    cam.current.lookAt(0, 1.6, -0.4)
  })

  return (
    <>
      <color attach="background" args={['#0c0818']} />
      <fog attach="fog" args={['#160e28', 10, 28]} />
      <PerspectiveCamera ref={cam} makeDefault fov={42} near={0.1} far={80} position={[0, 2.6, 5.8]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[4, 8, 3]} intensity={0.7} color="#ffe9c8" />
      <pointLight position={[0, 3.2, 1]} intensity={1.2} color="#fff0b0" distance={14} />

      {/* floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0.4]} receiveShadow>
        <planeGeometry args={[16, 10]} />
        <meshStandardMaterial color="#1a1624" roughness={0.85} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0.2]}>
        <planeGeometry args={[12, 6]} />
        <meshStandardMaterial color="#cfc4b0" roughness={0.45} metalness={0.08} />
      </mesh>
      {/* brass inlay */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0.2]}>
        <ringGeometry args={[1.6, 1.72, 48]} />
        <meshBasicMaterial color={BRASS} />
      </mesh>

      {/* back wall */}
      <mesh position={[0, 2.1, -3.1]}>
        <boxGeometry args={[14, 4.4, 0.2]} />
        <meshStandardMaterial color="#241c34" roughness={0.88} />
      </mesh>
      <mesh position={[0, 0.55, -3.0]}>
        <boxGeometry args={[14, 1.1, 0.08]} />
        <meshStandardMaterial color="#1a1428" roughness={0.7} />
      </mesh>

      {/* side walls */}
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[side * 6.8, 2.1, -0.2]} rotation={[0, -side * Math.PI / 2, 0]}>
          <planeGeometry args={[8, 4.4]} />
          <meshStandardMaterial color="#1e1830" roughness={0.9} />
        </mesh>
      ))}

      {/* ceiling */}
      <mesh position={[0, 4.05, -0.2]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[14, 8]} />
        <meshStandardMaterial color="#140e22" roughness={0.95} />
      </mesh>
      {([-2.2, 0, 2.2] as const).map((x) => (
        <mesh key={x} position={[x, 3.95, -0.4]}>
          <boxGeometry args={[0.35, 0.06, 4.5]} />
          <meshBasicMaterial color="#e7f6ff" toneMapped={false} />
        </mesh>
      ))}

      <ProfitBoard desk={desk} />

      {/* teller row */}
      {tellers.map((bot, i) => (
        <TellerStation
          key={bot?.id || `empty-${i}`}
          bot={bot}
          index={i}
          x={(i - 2) * 2.35}
          onSelect={onSelectTeller}
        />
      ))}

      {/* lobby plaque */}
      <Html position={[0, 0.35, 2.4]} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
        <div
          style={{
            fontFamily: 'IBM Plex Mono, monospace',
            fontSize: '12px',
            color: '#f9c80e',
            letterSpacing: '0.12em',
            textAlign: 'center',
            textShadow: '0 0 12px rgba(249,200,14,0.45)',
          }}
        >
          APEX-CITY TRUST · {workers} TELLERS ON DUTY
          <div style={{ color: '#9aa3c7', marginTop: 4, letterSpacing: '0.04em' }}>
            cash {money(desk?.cash)} · click a teller for trades
          </div>
          <div className={`tone-${pnlTone(desk?.realized)}`} style={{ marginTop: 2 }}>
            net {money(desk?.realized, true)}
          </div>
        </div>
      </Html>

      <NeonBloom strength={0.75} />
    </>
  )
}
