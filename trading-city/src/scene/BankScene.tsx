import { useEffect, useMemo, useRef } from 'react'
import { Html, OrbitControls, PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { DoubleSide, type Group, type Mesh } from 'three'
import type { BotRow, Desk } from '../types'
import { BEAM_COLORS, money, workersOnShift } from '../data/format'
import { botPose } from '../data/botPose'
import {
  tellerPlateTexture,
  vaultBoardTexture,
  vaultComplianceTexture,
  vaultLedgerTexture,
} from '../hud/monitorTextures'
import { NeonBloom } from './Effects'
import { BotFigure } from './BotFigure'

type Props = {
  bots: BotRow[]
  desk?: Desk
  onSelectTeller: (id: string) => void
}

/** Office-matched synthwave trust hall — purple shell, cyan trim, amber chrome. */
const WALL = '#241848'
const WALL_DEEP = '#160e2c'
const WAINSCOT = '#1b212e'
const TRIM = '#7ec8d8'
const BRASS = '#c9a227'
const INK = '#050812'
const FLOOR = '#0e061c'

const HOME_POS: [number, number, number] = [0, 2.55, 6.4]
const HOME_TARGET: [number, number, number] = [0, 1.45, -0.6]

function TellerPod({
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
  const plate = useMemo(() => tellerPlateTexture(bot, index, color), [bot, index, color])
  const lamp = useRef<Mesh>(null)
  const halo = useRef<Mesh>(null)

  useEffect(() => () => plate.dispose(), [plate])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (lamp.current) {
      const mat = lamp.current.material as { emissiveIntensity?: number }
      if (mat.emissiveIntensity != null) {
        mat.emissiveIntensity = offline ? 0.2 : 0.65 + Math.sin(t * 2.6 + index) * 0.22
      }
    }
    if (halo.current) {
      const s = 1 + Math.sin(t * 1.8 + index) * 0.04
      halo.current.scale.set(s, 1, s)
    }
  })

  const select = (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    if (bot) onSelect(bot.id)
  }

  return (
    <group position={[x, 0, -0.05]}>
      {/* open trading pod — low counter so the full bot reads */}
      <mesh position={[0, 0.42, -0.15]}>
        <boxGeometry args={[1.7, 0.84, 0.7]} />
        <meshStandardMaterial color="#14101c" roughness={0.72} metalness={0.22} />
      </mesh>
      <mesh position={[0, 0.86, 0.18]} castShadow>
        <boxGeometry args={[1.78, 0.08, 0.95]} />
        <meshStandardMaterial color="#d8d0c0" roughness={0.28} metalness={0.22} />
      </mesh>
      <mesh position={[0, 0.83, 0.64]}>
        <boxGeometry args={[1.78, 0.025, 0.03]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.7} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.87, 0.66]}>
        <boxGeometry args={[1.78, 0.03, 0.045]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
      </mesh>

      {/* side glass fins only — open sightline to the bot */}
      {([-0.86, 0.86] as const).map((sx) => (
        <group key={sx}>
          <mesh position={[sx, 1.45, -0.05]}>
            <boxGeometry args={[0.04, 1.15, 0.7]} />
            <meshStandardMaterial color="#7ef9ff" transparent opacity={0.1} metalness={0.3} roughness={0.08} />
          </mesh>
          <mesh position={[sx, 2.05, -0.05]}>
            <boxGeometry args={[0.06, 0.05, 0.72]} />
            <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.28} />
          </mesh>
        </group>
      ))}

      {/* desk terminal + lamp */}
      <mesh position={[-0.45, 1.05, 0.28]} rotation={[-0.4, 0.12, 0]}>
        <boxGeometry args={[0.48, 0.3, 0.03]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} />
      </mesh>
      <mesh position={[-0.45, 1.05, 0.3]} rotation={[-0.4, 0.12, 0]}>
        <planeGeometry args={[0.4, 0.24]} />
        <meshBasicMaterial color={offline ? '#2a1830' : color} transparent opacity={0.55} toneMapped={false} />
      </mesh>
      <mesh position={[0.55, 0.95, 0.15]}>
        <cylinderGeometry args={[0.03, 0.04, 0.08, 10]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh position={[0.55, 1.12, 0.15]}>
        <cylinderGeometry args={[0.01, 0.01, 0.22, 8]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh ref={lamp} position={[0.55, 1.24, 0.26]} rotation={[0.55, 0, 0]}>
        <coneGeometry args={[0.08, 0.11, 12, 1, true]} />
        <meshStandardMaterial
          color="#1a1420"
          emissive={offline ? '#401820' : '#fff0b0'}
          emissiveIntensity={0.7}
          side={DoubleSide}
          roughness={0.4}
        />
      </mesh>

      {/* sharp canvas nameplate */}
      <mesh position={[0, 1.72, 0.42]} onClick={select} onPointerOver={() => bot && (document.body.style.cursor = 'pointer')} onPointerOut={() => (document.body.style.cursor = 'default')}>
        <boxGeometry args={[1.35, 0.42, 0.05]} />
        <meshStandardMaterial color={INK} metalness={0.35} roughness={0.4} />
      </mesh>
      <mesh position={[0, 1.72, 0.45]} onClick={select}>
        <planeGeometry args={[1.25, 0.36]} />
        <meshBasicMaterial map={plate} toneMapped={false} />
      </mesh>

      {/* standing teller — full silhouette like the office bot */}
      <group position={[0, 0.02, -0.42]} scale={0.88}>
        <BotFigure pose={pose} seated={false} />
      </group>

      {/* approach halo */}
      <mesh
        ref={halo}
        position={[0, 0.02, 1.15]}
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={select}
        onPointerOver={() => bot && (document.body.style.cursor = 'pointer')}
        onPointerOut={() => (document.body.style.cursor = 'default')}
      >
        <ringGeometry args={[0.45, 0.62, 40]} />
        <meshBasicMaterial color={color} transparent opacity={0.7} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.015, 1.15]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.42, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.14} />
      </mesh>
      <pointLight position={[0, 2.2, 0.2]} intensity={offline ? 0.15 : 0.35} color={color} distance={4.5} />
    </group>
  )
}

function ProfitBoard({ desk }: { desk?: Desk }) {
  const map = useMemo(() => vaultBoardTexture(desk), [desk])
  useFrame(() => {
    map.needsUpdate = true
  })
  return (
    <group position={[0, 3.2, -2.72]}>
      <mesh>
        <boxGeometry args={[7.0, 1.28, 0.14]} />
        <meshStandardMaterial color={INK} metalness={0.5} roughness={0.28} />
      </mesh>
      <mesh position={[0, 0, 0.08]}>
        <planeGeometry args={[6.55, 1.05]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.68, 0.05]}>
        <boxGeometry args={[7.1, 0.045, 0.08]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.68, 0.05]}>
        <boxGeometry args={[7.1, 0.045, 0.08]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
      </mesh>
      {([-3.25, 3.25] as const).map((x) =>
        ([-0.45, 0.45] as const).map((y) => (
          <mesh key={`${x}-${y}`} position={[x, y, 0.1]}>
            <cylinderGeometry args={[0.04, 0.04, 0.035, 10]} />
            <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.2} />
          </mesh>
        )),
      )}
    </group>
  )
}

/** Hero circular vault door — the visual anchor the old lobby never had. */
function HeroVaultDoor() {
  const dial = useRef<Group>(null)
  const ring = useRef<Mesh>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (dial.current) dial.current.rotation.z = t * 0.28
    if (ring.current) {
      const mat = ring.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = 0.28 + Math.sin(t * 1.5) * 0.1
    }
  })
  const bolts = Array.from({ length: 14 }, (_, i) => {
    const a = (i / 14) * Math.PI * 2
    return [Math.cos(a) * 1.05, Math.sin(a) * 1.05] as const
  })
  return (
    <group position={[0, 1.55, -2.98]}>
      <mesh position={[0, 0, -0.06]}>
        <cylinderGeometry args={[1.45, 1.45, 0.18, 48]} />
        <meshStandardMaterial color="#0a0614" metalness={0.6} roughness={0.32} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[1.28, 1.28, 0.2, 48]} />
        <meshStandardMaterial color="#2a2438" metalness={0.75} roughness={0.24} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, 0.06]}>
        <cylinderGeometry args={[1.05, 1.05, 0.16, 48]} />
        <meshStandardMaterial color="#14101c" metalness={0.7} roughness={0.28} />
      </mesh>
      {Array.from({ length: 8 }).map((_, i) => {
        const a = (i / 8) * Math.PI
        return (
          <mesh key={i} position={[0, 0, 0.14]} rotation={[0, 0, a]}>
            <boxGeometry args={[2.05, 0.055, 0.04]} />
            <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
          </mesh>
        )
      })}
      {bolts.map(([bx, by], i) => (
        <mesh key={i} position={[bx, by, 0.18]}>
          <cylinderGeometry args={[0.055, 0.055, 0.05, 8]} />
          <meshStandardMaterial color="#8a7a40" metalness={0.8} roughness={0.28} />
        </mesh>
      ))}
      <group ref={dial} position={[0, 0, 0.22]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.32, 0.05, 12, 28]} />
          <meshStandardMaterial color={BRASS} metalness={0.9} roughness={0.18} emissive={BRASS} emissiveIntensity={0.35} />
        </mesh>
        <mesh>
          <boxGeometry args={[0.5, 0.045, 0.045]} />
          <meshBasicMaterial color="#f9c80e" toneMapped={false} />
        </mesh>
        <mesh rotation={[0, 0, Math.PI / 2]}>
          <boxGeometry args={[0.28, 0.035, 0.035]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
      </group>
      <mesh ref={ring} position={[0, 0, 0.1]}>
        <ringGeometry args={[1.28, 1.42, 48]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.3} depthWrite={false} toneMapped={false} />
      </mesh>
      <pointLight position={[0, 0, 0.6]} intensity={0.55} color="#fff0b0" distance={5} />
    </group>
  )
}

function Column({ x, z }: { x: number; z: number }) {
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 2.1, 0]}>
        <cylinderGeometry args={[0.2, 0.24, 4.2, 14]} />
        <meshStandardMaterial color="#1a1428" roughness={0.65} metalness={0.25} />
      </mesh>
      <mesh position={[0, 0.08, 0]}>
        <cylinderGeometry args={[0.32, 0.34, 0.16, 14]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.28} />
      </mesh>
      <mesh position={[0, 4.05, 0]}>
        <cylinderGeometry args={[0.34, 0.28, 0.16, 14]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.28} />
      </mesh>
      {[1.15, 2.1, 3.05].map((y) => (
        <mesh key={y} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.24, 0.02, 8, 22]} />
          <meshBasicMaterial color="#2de2e6" toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

function TrustSeal({ workers }: { workers: number }) {
  const core = useRef<Mesh>(null)
  const spin = useRef<Mesh>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (core.current) {
      core.current.rotation.y = t * 0.7
      core.current.position.y = 0.28 + Math.sin(t * 1.9) * 0.04
    }
    if (spin.current) spin.current.rotation.z = -t * 0.3
  })
  return (
    <group position={[0, 0.02, 1.7]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.45, 1.62, 64]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.004, 0]}>
        <ringGeometry args={[1.12, 1.22, 64]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.75} toneMapped={false} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.002, 0]}>
        <circleGeometry args={[1.1, 64]} />
        <meshStandardMaterial color="#0a0618" metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh ref={spin} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <ringGeometry args={[0.58, 0.66, 40]} />
        <meshBasicMaterial color="#b967ff" transparent opacity={0.8} toneMapped={false} />
      </mesh>
      {/* extruded brand marks — geometry, not floating HTML */}
      {Array.from({ length: 8 }).map((_, i) => {
        const a = (i / 8) * Math.PI * 2
        return (
          <mesh key={i} position={[Math.cos(a) * 0.88, 0.03, Math.sin(a) * 0.88]} rotation={[-Math.PI / 2, 0, -a]}>
            <boxGeometry args={[0.06, 0.22, 0.02]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
        )
      })}
      <mesh ref={core} position={[0, 0.28, 0]}>
        <octahedronGeometry args={[0.26, 0]} />
        <meshBasicMaterial color="#7ef9ff" transparent opacity={0.92} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.28, 0]}>
        <octahedronGeometry args={[0.12, 0]} />
        <meshBasicMaterial color="#fff4b8" toneMapped={false} />
      </mesh>
      <Html position={[0, 0.72, 0]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
        <div
          style={{
            fontFamily: 'Orbitron, sans-serif',
            fontSize: '11px',
            color: '#f9c80e',
            letterSpacing: '0.14em',
            textAlign: 'center',
            textShadow: '0 0 14px rgba(249,200,14,0.5)',
          }}
        >
          APEX-CITY TRUST
          <div style={{ color: '#9aa3c7', marginTop: 3, fontSize: '10px', letterSpacing: '0.08em' }}>
            {workers} TELLERS ON DUTY
          </div>
        </div>
      </Html>
    </group>
  )
}

function LockboxWall({ bots }: { bots: BotRow[] }) {
  const cells = []
  for (let row = 0; row < 5; row++) {
    for (let col = 0; col < 3; col++) {
      const i = row * 3 + col
      const bot = bots[i % Math.max(bots.length, 1)]
      cells.push({
        x: col * 0.38 - 0.38,
        y: row * 0.34 + 1.0,
        lit: Boolean(bot && bot.present !== false),
        color: BEAM_COLORS[i % BEAM_COLORS.length],
      })
    }
  }
  return (
    <group position={[-5.4, 0, -1.5]} rotation={[0, 0.5, 0]}>
      <mesh position={[0, 1.9, -0.05]}>
        <boxGeometry args={[1.5, 2.7, 0.14]} />
        <meshStandardMaterial color="#12101a" metalness={0.5} roughness={0.35} />
      </mesh>
      {cells.map((c, i) => (
        <group key={i} position={[c.x, c.y, 0.05]}>
          <mesh>
            <boxGeometry args={[0.32, 0.28, 0.08]} />
            <meshStandardMaterial color="#1c1828" metalness={0.55} roughness={0.32} />
          </mesh>
          <mesh position={[0.1, 0, 0.05]}>
            <boxGeometry args={[0.035, 0.05, 0.02]} />
            <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
          </mesh>
          <mesh position={[-0.08, 0.06, 0.05]}>
            <sphereGeometry args={[0.025, 8, 8]} />
            <meshBasicMaterial color={c.lit ? c.color : '#332240'} toneMapped={false} />
          </mesh>
        </group>
      ))}
      <mesh position={[0, 3.3, 0.05]}>
        <boxGeometry args={[1.35, 0.08, 0.04]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
    </group>
  )
}

function CountingCage() {
  return (
    <group position={[5.15, 0, -1.35]} rotation={[0, -0.45, 0]}>
      <mesh position={[0, 1.1, 0]}>
        <boxGeometry args={[1.5, 2.15, 1.0]} />
        <meshStandardMaterial color="#14101c" roughness={0.7} metalness={0.25} />
      </mesh>
      <mesh position={[0, 1.35, 0.52]}>
        <boxGeometry args={[1.1, 0.8, 0.04]} />
        <meshStandardMaterial color={INK} roughness={0.45} />
      </mesh>
      {([-0.38, -0.19, 0, 0.19, 0.38] as const).map((x) => (
        <mesh key={x} position={[x, 1.35, 0.54]}>
          <boxGeometry args={[0.03, 0.8, 0.03]} />
          <meshStandardMaterial color={BRASS} metalness={0.75} roughness={0.28} />
        </mesh>
      ))}
      {[
        [-0.3, 0.52, 0.12],
        [0.12, 0.52, -0.08],
        [0.3, 0.6, 0.18],
      ].map((p, i) => (
        <mesh key={i} position={p as [number, number, number]}>
          <boxGeometry args={[0.26, 0.1 + i * 0.03, 0.16]} />
          <meshStandardMaterial color={i % 2 ? '#39ff14' : '#1a6b3a'} emissive="#0a3a20" emissiveIntensity={0.4} />
        </mesh>
      ))}
      <mesh position={[0, 2.25, 0.52]}>
        <boxGeometry args={[1.15, 0.07, 0.05]} />
        <meshBasicMaterial color="#39ff14" toneMapped={false} />
      </mesh>
    </group>
  )
}

function SideScreen({
  side,
  desk,
  bots,
}: {
  side: -1 | 1
  desk?: Desk
  bots: BotRow[]
}) {
  const map = useMemo(
    () => (side < 0 ? vaultLedgerTexture(desk, bots) : vaultComplianceTexture(desk, bots)),
    [side, desk, bots],
  )
  useFrame(() => {
    map.needsUpdate = true
  })
  return (
    <group position={[side * 5.15, 2.4, 1.0]} rotation={[0, -side * 0.9, 0]}>
      <mesh>
        <boxGeometry args={[2.2, 1.45, 0.08]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} />
      </mesh>
      <mesh position={[0, 0, 0.05]}>
        <planeGeometry args={[2.0, 1.25]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.76, 0.04]}>
        <boxGeometry args={[2.25, 0.035, 0.045]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
    </group>
  )
}

function CeilingHall() {
  return (
    <group>
      <mesh position={[0, 4.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[14.5, 9.2]} />
        <meshStandardMaterial color="#100a1e" roughness={0.95} side={DoubleSide} />
      </mesh>
      {/* coffered beams */}
      {([-2.6, -0.85, 0.85, 2.6] as const).map((x) => (
        <group key={x}>
          <mesh position={[x, 4.08, -0.15]}>
            <boxGeometry args={[0.22, 0.16, 7.2]} />
            <meshStandardMaterial color="#1a1428" roughness={0.7} metalness={0.2} />
          </mesh>
          <mesh position={[x, 4.0, -0.15]}>
            <boxGeometry args={[0.38, 0.05, 5.6]} />
            <meshBasicMaterial color="#e7f6ff" toneMapped={false} />
          </mesh>
          {/* soft shaft */}
          <mesh position={[x, 2.3, -0.15]}>
            <boxGeometry args={[0.12, 3.4, 4.8]} />
            <meshBasicMaterial color="#fff6d8" transparent opacity={0.035} depthWrite={false} />
          </mesh>
        </group>
      ))}
      <mesh position={[0, 4.0, -3.0]}>
        <boxGeometry args={[14, 0.12, 0.2]} />
        <meshStandardMaterial color={TRIM} metalness={0.4} roughness={0.4} />
      </mesh>
      {/* mezzanine rail hint */}
      <mesh position={[0, 3.35, -2.55]}>
        <boxGeometry args={[12.5, 0.04, 0.04]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
    </group>
  )
}

function DataMotes() {
  const ref = useRef<Group>(null)
  const motes = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        x: ((i * 47) % 100) / 100 * 8 - 4,
        z: ((i * 31) % 100) / 100 * 4 - 1.5,
        phase: i * 0.7,
        speed: 0.35 + (i % 5) * 0.08,
        color: BEAM_COLORS[i % BEAM_COLORS.length],
      })),
    [],
  )
  useFrame(({ clock }) => {
    if (!ref.current) return
    const t = clock.getElapsedTime()
    ref.current.children.forEach((child, i) => {
      const m = motes[i]
      child.position.y = 0.4 + ((t * m.speed + m.phase) % 3.2)
      child.rotation.y = t * 0.8 + m.phase
    })
  })
  return (
    <group ref={ref}>
      {motes.map((m, i) => (
        <mesh key={i} position={[m.x, 0.5, m.z]}>
          <boxGeometry args={[0.05, 0.05, 0.05]} />
          <meshBasicMaterial color={m.color} transparent opacity={0.55} toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

function Warden() {
  return (
    <group position={[3.4, 0.05, -2.05]} rotation={[0, -0.4, 0]} scale={0.92}>
      <BotFigure pose="waiting" seated={false} />
      <mesh position={[0, 2.15, 0.05]}>
        <boxGeometry args={[0.9, 0.14, 0.04]} />
        <meshStandardMaterial color={INK} emissive="#ff2a6d" emissiveIntensity={0.45} />
      </mesh>
      <mesh position={[0, 2.15, 0.08]}>
        <planeGeometry args={[0.82, 0.1]} />
        <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
      </mesh>
    </group>
  )
}

function FloorGlowPaths() {
  return (
    <group>
      {([-2, -1, 0, 1, 2] as const).map((i) => (
        <mesh key={i} position={[i * 1.25, 0.012, 0.4]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.06, 2.4]} />
          <meshBasicMaterial
            color={BEAM_COLORS[(i + 2) % BEAM_COLORS.length]}
            transparent
            opacity={0.28}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  )
}

function CompliancePillar() {
  return (
    <group position={[-4.2, 0, 2.4]}>
      <mesh position={[0, 0.9, 0]}>
        <boxGeometry args={[0.55, 1.75, 0.55]} />
        <meshStandardMaterial color="#1a1230" roughness={0.65} metalness={0.25} />
      </mesh>
      <mesh position={[0, 1.8, 0]}>
        <boxGeometry args={[0.58, 0.08, 0.58]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.15, 0.29]}>
        <planeGeometry args={[0.4, 0.7]} />
        <meshBasicMaterial color={INK} />
      </mesh>
      <Html position={[0, 1.15, 0.32]} center distanceFactor={7.5} style={{ pointerEvents: 'none' }}>
        <div
          style={{
            fontFamily: 'Orbitron, sans-serif',
            fontSize: '10px',
            color: '#f9c80e',
            textAlign: 'center',
            letterSpacing: '0.1em',
            lineHeight: 1.35,
          }}
        >
          PAPER
          <br />
          ONLY
        </div>
      </Html>
    </group>
  )
}

function NightDeposit() {
  const slot = useRef<Mesh>(null)
  useFrame(({ clock }) => {
    if (!slot.current) return
    const mat = slot.current.material as { emissiveIntensity?: number }
    if (mat.emissiveIntensity != null) mat.emissiveIntensity = 0.45 + Math.sin(clock.getElapsedTime() * 2.2) * 0.25
  })
  return (
    <group position={[4.4, 0.95, 2.2]} rotation={[0, -0.9, 0]}>
      <mesh>
        <boxGeometry args={[0.85, 1.3, 0.32]} />
        <meshStandardMaterial color="#16101f" roughness={0.6} metalness={0.28} />
      </mesh>
      <mesh ref={slot} position={[0, 0.12, 0.17]}>
        <boxGeometry args={[0.5, 0.07, 0.04]} />
        <meshStandardMaterial color={INK} emissive="#2de2e6" emissiveIntensity={0.55} />
      </mesh>
      <mesh position={[0, 0.48, 0.17]}>
        <boxGeometry args={[0.55, 0.16, 0.03]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
    </group>
  )
}

function WaitingBench({ x }: { x: number }) {
  return (
    <group position={[x, 0, 3.0]}>
      <mesh position={[0, 0.28, 0]}>
        <boxGeometry args={[1.35, 0.08, 0.4]} />
        <meshStandardMaterial color="#1c1828" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.48, -0.15]}>
        <boxGeometry args={[1.35, 0.32, 0.06]} />
        <meshStandardMaterial color="#241c34" roughness={0.65} />
      </mesh>
      <mesh position={[0, 0.25, 0.18]}>
        <boxGeometry args={[1.38, 0.02, 0.02]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
    </group>
  )
}

function Stanchion({ position, color }: { position: [number, number, number]; color: string }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.42, 0]}>
        <cylinderGeometry args={[0.032, 0.038, 0.84, 10]} />
        <meshStandardMaterial color="#1a1424" metalness={0.45} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.86, 0]}>
        <sphereGeometry args={[0.065, 12, 12]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} emissive={color} emissiveIntensity={0.4} />
      </mesh>
      <mesh position={[0, 0.04, 0]}>
        <cylinderGeometry args={[0.09, 0.11, 0.05, 10]} />
        <meshStandardMaterial color="#121018" roughness={0.55} />
      </mesh>
    </group>
  )
}

/** Interior APEX-CITY TRUST — neon bank hall with hero vault door + open teller pods. */
export function BankScene({ bots, desk, onSelectTeller }: Props) {
  const controls = useRef<OrbitControlsImpl>(null)
  const tellers = useMemo(() => {
    const list: (BotRow | null)[] = [...bots]
    while (list.length < 5) list.push(null)
    return list.slice(0, 5)
  }, [bots])
  const workers = workersOnShift(bots)

  useEffect(() => {
    const orbit = controls.current
    const cam = orbit?.object
    if (!orbit || !cam) return
    cam.position.set(...HOME_POS)
    orbit.target.set(...HOME_TARGET)
    orbit.update()
  }, [])

  return (
    <>
      <color attach="background" args={['#12082a']} />
      <fog attach="fog" args={['#1a0a38', 10, 26]} />
      <PerspectiveCamera makeDefault fov={40} near={0.08} far={80} position={HOME_POS} />
      <OrbitControls
        ref={controls}
        makeDefault
        target={HOME_TARGET}
        enableDamping
        dampingFactor={0.08}
        enablePan={false}
        minDistance={4.2}
        maxDistance={9.5}
        minPolarAngle={0.85}
        maxPolarAngle={1.45}
        minAzimuthAngle={-0.85}
        maxAzimuthAngle={0.85}
      />

      <ambientLight intensity={0.42} color="#c8b8ff" />
      <directionalLight position={[3.2, 7.2, 2.8]} intensity={0.55} color="#ffe9c8" />
      <pointLight position={[0, 3.5, 0.6]} intensity={1.1} color="#fff0b0" distance={14} />
      <pointLight position={[-2.4, 3.0, -0.4]} intensity={0.4} color="#7ef9ff" distance={9} />
      <pointLight position={[2.4, 3.0, -0.4]} intensity={0.4} color="#b967ff" distance={9} />

      {/* floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0.35]} receiveShadow>
        <planeGeometry args={[15, 10]} />
        <meshStandardMaterial color={FLOOR} roughness={0.55} metalness={0.28} side={DoubleSide} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.006, 0.2]}>
        <planeGeometry args={[11.5, 6.2]} />
        <meshStandardMaterial color="#160e2c" roughness={0.4} metalness={0.35} />
      </mesh>
      <gridHelper args={[10, 20, '#2de2e6', '#2a1060']} position={[0, 0.012, 0.25]} />
      <FloorGlowPaths />

      {/* shell */}
      <mesh position={[0, 2.15, -3.2]}>
        <boxGeometry args={[14.5, 4.5, 0.25]} />
        <meshStandardMaterial color={WALL} roughness={0.88} />
      </mesh>
      <mesh position={[0, 0.55, -3.05]}>
        <boxGeometry args={[14.5, 1.15, 0.1]} />
        <meshStandardMaterial color={WAINSCOT} roughness={0.8} />
      </mesh>
      <mesh position={[0, 1.12, -3.02]}>
        <boxGeometry args={[14.5, 0.04, 0.05]} />
        <meshStandardMaterial color={TRIM} metalness={0.4} roughness={0.4} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <group key={side}>
          <mesh position={[side * 6.9, 2.15, 0]} rotation={[0, -side * (Math.PI / 2), 0]}>
            <planeGeometry args={[9.2, 4.5]} />
            <meshStandardMaterial color={WALL_DEEP} roughness={0.9} side={DoubleSide} />
          </mesh>
          <mesh position={[side * 6.82, 0.55, 0]} rotation={[0, -side * (Math.PI / 2), 0]}>
            <planeGeometry args={[9.2, 1.15]} />
            <meshStandardMaterial color={WAINSCOT} roughness={0.8} side={DoubleSide} />
          </mesh>
        </group>
      ))}

      <CeilingHall />
      <Column x={-4.5} z={-2.4} />
      <Column x={4.5} z={-2.4} />
      <Column x={-4.5} z={1.5} />
      <Column x={4.5} z={1.5} />

      <HeroVaultDoor />
      <ProfitBoard desk={desk} />
      <LockboxWall bots={bots} />
      <CountingCage />
      <SideScreen side={-1} desk={desk} bots={bots} />
      <SideScreen side={1} desk={desk} bots={bots} />
      <TrustSeal workers={workers} />
      <Warden />
      <CompliancePillar />
      <NightDeposit />
      <WaitingBench x={-2.3} />
      <WaitingBench x={2.3} />
      <DataMotes />

      {tellers.map((_, i) => {
        const x = (i - 2) * 2.25
        const color = BEAM_COLORS[i % BEAM_COLORS.length]
        return (
          <group key={`stanchion-${i}`}>
            <Stanchion position={[x, 0, 1.85]} color={color} />
            <Stanchion position={[x, 0, 1.0]} color={color} />
            <mesh position={[x, 0.78, 1.42]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.016, 0.016, 0.85, 6]} />
              <meshBasicMaterial color={color} toneMapped={false} />
            </mesh>
          </group>
        )
      })}

      {tellers.map((bot, i) => (
        <TellerPod
          key={bot?.id || `empty-${i}`}
          bot={bot}
          index={i}
          x={(i - 2) * 2.25}
          onSelect={onSelectTeller}
        />
      ))}

      <Html position={[0, 0.1, 3.5]} center distanceFactor={12} style={{ pointerEvents: 'none' }}>
        <div
          style={{
            fontFamily: 'Share Tech Mono, monospace',
            fontSize: '11px',
            color: '#9aa3c7',
            textAlign: 'center',
            letterSpacing: '0.06em',
          }}
        >
          drag to look · cash {money(desk?.cash)} · click a teller pad
        </div>
      </Html>

      <NeonBloom strength={0.55} />
    </>
  )
}
