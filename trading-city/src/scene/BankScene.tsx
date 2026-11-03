import { useEffect, useMemo, useRef, useState } from 'react'
import { Html, PerspectiveCamera } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { DoubleSide, MathUtils, type Group, type Mesh } from 'three'
import type { BotRow, Desk } from '../types'
import { BEAM_COLORS, beamColorFor, workersOnShift } from '../data/format'
import { botPose } from '../data/botPose'
import {
  sharpenBoardTexture,
  tellerPlateTexture,
  vaultBoardTexture,
  vaultComplianceTexture,
  vaultLedgerTexture,
} from '../hud/monitorTextures'
import { NeonBloom } from './Effects'
import { BotFigure } from './BotFigure'
import { PlayerBot } from './PlayerBot'

type Props = {
  bots: BotRow[]
  desk?: Desk
  onSelectTeller: (id: string) => void
  /** Open the 2D desk ops board (budgets / adapt / fill tax) from a ledger click. */
  onOpenDeskOps?: () => void
  /** Live control hint for the grounded player. */
  onWalkHint?: (hint: string) => void
}

/** Office-matched synthwave trust hall — purple shell, cyan trim, amber chrome. */
const WALL = '#241848'
const WAINSCOT = '#1b212e'
const TRIM = '#7ec8d8'
const BRASS = '#c9a227'
const INK = '#050812'
const FLOOR = '#0e061c'

/**
 * Dual banks + clear center aisle to the vault.
 * Bots stand on the wall side; ropes sit on the aisle (inside); desks face the path.
 * Fixed 12 slots (6 left + 6 right).
 */
const SIDE_COUNT = 6
const TOTAL_SLOTS = SIDE_COUNT * 2
const TELLER_SPACING = 2.05
/** Desk origin distance from aisle centerline. */
const AISLE_HALF = 3.35
/** Frontmost row (toward portal); rows step toward the vault (−Z). */
const TELLER_Z0 = 2.4
/** Tight enclosed vault — walls sit just outside the teller pods so the room reads. */
const HALL_W = 12.2
const Z_BACK = -11.5
const Z_FRONT = 7.5
const HALL_HEIGHT = 4.8
const HOME_POS: [number, number, number] = [0, 1.62, 5.2]
/** Half-width of each teller's private rope channel (local X). */
const LANE_HALF = 0.58
/**
 * Queue ropes fully forward of the desk counter (lip ≈ +0.2).
 * Keep LANE_Z_BACK well clear so stanchions never intersect cabinets.
 */
const LANE_Z_MOUTH = 2.35
const LANE_Z_MID = 1.65
const LANE_Z_BACK = 1.15
const ROPE_Y = 0.82

type SlotPose = {
  side: -1 | 1
  row: number
  x: number
  z: number
  rotY: number
}

/**
 * Left = 0..5, right = 6..11 (tellers 7–12).
 * Local +Z = customer approach toward the aisle.
 * Left rotY=+π/2 → local +Z → world +X (into the path).
 * Right rotY=−π/2 → local +Z → world −X.
 * Bot stands at local −Z (wall); ropes at local +Z (aisle), clear of the desk.
 */
function slotPose(index: number): SlotPose {
  const side: -1 | 1 = index < SIDE_COUNT ? -1 : 1
  const row = index % SIDE_COUNT
  const z = TELLER_Z0 - row * TELLER_SPACING
  const x = side * AISLE_HALF
  const rotY = side < 0 ? Math.PI / 2 : -Math.PI / 2
  return { side, row, x, z, rotY }
}

function tellerSlots(bots: BotRow[]): (BotRow | null)[] {
  const list: (BotRow | null)[] = bots.slice(0, TOTAL_SLOTS)
  while (list.length < TOTAL_SLOTS) list.push(null)
  return list
}

function TellerPod({
  bot,
  index,
  focused,
  away,
  recalling,
  onSelect,
}: {
  bot: BotRow | null
  index: number
  focused: boolean
  away: boolean
  recalling: boolean
  onSelect: (id: string) => void
}) {
  // Parent orients local +Z toward the aisle. Desk stays compact; bot stands behind it.
  const color = beamColorFor(bot?.id, index)
  const offline = !bot || bot.present === false
  const pose = bot ? botPose(bot) : 'waiting'
  const plate = useMemo(() => tellerPlateTexture(bot, index, color), [bot, index, color])
  const lamp = useRef<Mesh>(null)
  const halo = useRef<Mesh>(null)
  const botRoot = useRef<Group>(null)
  const walk = useRef({ z: 0, x: 0 })

  useEffect(() => () => plate.dispose(), [plate])
  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime()
    if (lamp.current) {
      const mat = lamp.current.material as { emissiveIntensity?: number }
      if (mat.emissiveIntensity != null) {
        mat.emissiveIntensity = offline ? 0.2 : (focused ? 0.85 : 0.55) + Math.sin(t * 2.4 + index) * 0.18
      }
    }
    if (halo.current) {
      const pulse = focused ? 0.08 : 0.035
      const s = 1 + Math.sin(t * 1.9 + index) * pulse
      halo.current.scale.set(s, 1, s)
    }
    // Step sideways into the open aisle when away — never through the desk.
    const targetZ = recalling ? 0 : away ? 0.15 : 0
    const targetX = recalling ? 0 : away ? (index % 2 === 0 ? -0.7 : 0.7) : 0
    walk.current.z = MathUtils.damp(walk.current.z, targetZ, 5.5, dt)
    walk.current.x = MathUtils.damp(walk.current.x, targetX, 5.5, dt)
    if (botRoot.current) {
      botRoot.current.position.x = walk.current.x
      botRoot.current.position.z = -1.28 + walk.current.z
      botRoot.current.rotation.y = Math.PI
    }
  })

  const select = (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    if (bot) onSelect(bot.id)
  }

  const podW = 1.4

  return (
    <group>
      {/* Pedestal */}
      <mesh position={[0, 0.07, -0.45]} receiveShadow>
        <boxGeometry args={[podW + 0.1, 0.14, 0.7]} />
        <meshStandardMaterial color="#1a1424" roughness={0.7} metalness={0.2} />
      </mesh>
      {/* Compact cabinet — back of station only */}
      <mesh position={[0, 0.48, -0.55]} castShadow>
        <boxGeometry args={[podW, 0.72, 0.48]} />
        <meshStandardMaterial
          color="#16121c"
          roughness={0.68}
          metalness={0.25}
          emissive={color}
          emissiveIntensity={offline ? 0.03 : focused ? 0.12 : 0.06}
        />
      </mesh>
      {[0.3, 0.5, 0.7].map((y) => (
        <mesh key={y} position={[0, y, -0.3]}>
          <boxGeometry args={[podW - 0.2, 0.014, 0.02]} />
          <meshStandardMaterial color="#2a2438" metalness={0.4} roughness={0.4} />
        </mesh>
      ))}
      {/* Short counter — front lip ≈ +0.18, well clear of ropes at 1.15+ */}
      <mesh position={[0, 0.88, -0.28]} castShadow>
        <boxGeometry args={[podW + 0.08, 0.07, 0.72]} />
        <meshStandardMaterial color="#d8d0c0" roughness={0.28} metalness={0.22} />
      </mesh>
      <mesh position={[0, 0.92, 0.06]}>
        <boxGeometry args={[podW * 0.5, 0.028, 0.035]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} emissive={color} emissiveIntensity={focused ? 0.3 : 0.14} />
      </mesh>
      {([-podW / 2 - 0.02, podW / 2 + 0.02] as const).map((sx) => (
        <mesh key={sx} position={[sx, 0.55, -0.5]}>
          <boxGeometry args={[0.022, 0.65, 0.4]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.28} toneMapped={false} />
        </mesh>
      ))}

      {([-0.74, 0.74] as const).map((sx) => (
        <group key={sx}>
          <mesh position={[sx, 1.3, -0.4]}>
            <boxGeometry args={[0.026, 0.75, 0.4]} />
            <meshStandardMaterial color="#7ef9ff" transparent opacity={0.07} metalness={0.3} roughness={0.15} depthWrite={false} />
          </mesh>
          <mesh position={[sx, 1.7, -0.4]}>
            <boxGeometry args={[0.035, 0.035, 0.42]} />
            <meshStandardMaterial color={BRASS} metalness={0.7} roughness={0.28} />
          </mesh>
        </group>
      ))}

      <mesh position={[-0.32, 1.0, -0.1]} rotation={[-0.35, 0.08, 0]}>
        <boxGeometry args={[0.36, 0.24, 0.03]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} emissive={color} emissiveIntensity={0.12} />
      </mesh>
      <mesh position={[-0.32, 1.0, -0.08]} rotation={[-0.35, 0.08, 0]}>
        <planeGeometry args={[0.3, 0.18]} />
        <meshBasicMaterial color={offline ? '#2a1830' : color} transparent opacity={0.55} toneMapped={false} />
      </mesh>
      <mesh position={[0.38, 0.94, -0.18]}>
        <cylinderGeometry args={[0.028, 0.036, 0.07, 10]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh position={[0.38, 1.08, -0.18]}>
        <cylinderGeometry args={[0.009, 0.009, 0.18, 8]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh ref={lamp} position={[0.38, 1.16, -0.06]} rotation={[0.45, 0, 0]}>
        <coneGeometry args={[0.07, 0.09, 12, 1, true]} />
        <meshStandardMaterial
          color="#1a1420"
          emissive={offline ? '#401820' : color}
          emissiveIntensity={0.7}
          side={DoubleSide}
          roughness={0.4}
        />
      </mesh>

      <mesh position={[0, 1.2, -0.62]}>
        <boxGeometry args={[0.055, 0.6, 0.055]} />
        <meshStandardMaterial color="#2a2438" metalness={0.5} roughness={0.35} />
      </mesh>
      <mesh
        position={[0, 1.58, -0.55]}
        onClick={select}
        onPointerOver={() => bot && (document.body.style.cursor = 'pointer')}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[1.22, 0.44, 0.05]} />
        <meshStandardMaterial color={INK} metalness={0.35} roughness={0.4} emissive={color} emissiveIntensity={focused ? 0.28 : 0.1} />
      </mesh>
      <mesh position={[0, 1.58, -0.52]} onClick={select}>
        <planeGeometry args={[1.12, 0.36]} />
        <meshBasicMaterial map={plate} toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.81, -0.53]}>
        <boxGeometry args={[1.24, 0.028, 0.028]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>

      {/* Teller well behind the cabinet — no desk intersection */}
      <group ref={botRoot} position={[0, 0.02, -1.28]} rotation={[0, Math.PI, 0]} scale={0.78}>
        <BotFigure pose={away && !recalling ? 'waiting' : pose} seated={false} />
      </group>

      {/* Approach halo at the rope mouth — in the open lane, not on the desk */}
      <mesh
        ref={halo}
        position={[0, 0.021, LANE_Z_MOUTH + 0.04]}
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={select}
        onPointerOver={() => bot && (document.body.style.cursor = 'pointer')}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <ringGeometry args={[focused ? 0.36 : 0.42, focused ? 0.6 : 0.54, 28]} />
        <meshBasicMaterial color={color} transparent opacity={focused ? 0.85 : 0.55} toneMapped={false} />
      </mesh>
      {away && !recalling && (
        <Html position={[0, 2.05, -0.7]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
          <div
            style={{
              fontFamily: 'Share Tech Mono, monospace',
              fontSize: '10px',
              color: '#9aa3c7',
              letterSpacing: '0.08em',
              whiteSpace: 'nowrap',
            }}
          >
            stepped away
          </div>
        </Html>
      )}
    </group>
  )
}

function ProfitBoard({ desk }: { desk?: Desk }) {
  const map = useMemo(() => vaultBoardTexture(desk), [desk])
  const { gl } = useThree()
  useEffect(() => {
    sharpenBoardTexture(map, gl.capabilities.getMaxAnisotropy())
  }, [gl, map])
  // Larger NET DESK board — readable when zoomed out in the bigger hall.
  return (
    <group position={[0, 4.15, Z_BACK + 0.55]}>
      <mesh>
        <boxGeometry args={[6.4, 1.12, 0.14]} />
        <meshStandardMaterial color={INK} metalness={0.5} roughness={0.28} />
      </mesh>
      <mesh position={[0, 0, 0.08]}>
        <planeGeometry args={[6.0, 0.92]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.6, 0.05]}>
        <boxGeometry args={[6.5, 0.045, 0.07]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.6, 0.05]}>
        <boxGeometry args={[6.5, 0.045, 0.07]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
      </mesh>
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
  // End of the center aisle, behind + below NET DESK — cyan ring clear of board faces.
  return (
    <group position={[0, 1.2, Z_BACK + 0.95]} scale={0.88}>
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
        <ringGeometry args={[1.15, 1.28, 48]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.26} depthWrite={false} toneMapped={false} />
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
      core.current.position.y = 0.22 + Math.sin(t * 1.9) * 0.03
    }
    if (spin.current) spin.current.rotation.z = -t * 0.3
  })
  // Portal apron — center of the T stem, clear of side queue mouths.
  return (
    <group position={[0, 0.02, 4.35]} scale={0.68}>
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
        color: beamColorFor(bot?.id, i),
      })
    }
  }
  return (
    <group position={[-HALL_W / 2 + 0.85, 0, Z_BACK + 2.4]} rotation={[0, 0.55, 0]}>
      <mesh position={[0, 1.5, -0.05]}>
        <boxGeometry args={[1.35, 2.2, 0.14]} />
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
    <group position={[HALL_W / 2 - 1.15, 0, Z_BACK + 2.6]} rotation={[0, -0.55, 0]}>
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
  onOpen,
}: {
  side: -1 | 1
  desk?: Desk
  bots: BotRow[]
  onOpen?: () => void
}) {
  const map = useMemo(
    () => (side < 0 ? vaultLedgerTexture(desk, bots) : vaultComplianceTexture(desk, bots)),
    [side, desk, bots],
  )
  const { gl } = useThree()
  useEffect(() => {
    sharpenBoardTexture(map, gl.capabilities.getMaxAnisotropy())
  }, [gl, map])
  // Larger far-readable boards flanking the vault — click opens desk ops HUD.
  const accent = side < 0 ? '#f9c80e' : '#39ff14'
  const open = (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    onOpen?.()
  }
  return (
    <group position={[side * 3.55, 2.55, Z_BACK + 0.55]}>
      <mesh
        onClick={open}
        onPointerOver={() => {
          document.body.style.cursor = onOpen ? 'pointer' : 'default'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[3.2, 1.5, 0.14]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} />
      </mesh>
      <mesh position={[0, 0, 0.08]} onClick={open}>
        <planeGeometry args={[2.95, 1.3]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.8, 0.06]}>
        <boxGeometry args={[3.25, 0.045, 0.06]} />
        <meshBasicMaterial color={accent} toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.8, 0.06]}>
        <boxGeometry args={[3.25, 0.04, 0.05]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      {onOpen && (
        <Html position={[0, -1.0, 0.1]} center distanceFactor={14} style={{ pointerEvents: 'none' }}>
          <div
            style={{
              fontFamily: 'Share Tech Mono, monospace',
              fontSize: '10px',
              color: accent,
              letterSpacing: '0.08em',
              whiteSpace: 'nowrap',
              opacity: 0.85,
            }}
          >
            click · desk ops
          </div>
        </Html>
      )}
    </group>
  )
}

/**
 * Square enclosed synthwave bank shell — portal front, vault wall at the far end.
 * Tellers sit on the four sides of the floor square.
 */
function BankEnclosure() {
  const width = HALL_W
  const halfW = width / 2
  const wallT = 0.32
  const zBack = Z_BACK
  const zFront = Z_FRONT
  const depth = zFront - zBack
  const midZ = (zFront + zBack) / 2
  const portalW = 3.8
  const sidePanelW = (width - portalW) / 2
  const sconceZ = [zBack + 2.2, -1.2, 2.0, zFront - 2.0]
  const ceilY = HALL_HEIGHT

  return (
    <group>
      {/* Solid floor — marble-dark bank slab + aisle carpet */}
      <mesh position={[0, -0.1, midZ]} receiveShadow>
        <boxGeometry args={[width + 0.6, 0.22, depth + 0.6]} />
        <meshStandardMaterial color={FLOOR} roughness={0.55} metalness={0.28} />
      </mesh>
      <mesh position={[0, 0.01, midZ]} receiveShadow>
        <boxGeometry args={[width - 0.2, 0.04, depth - 0.25]} />
        <meshStandardMaterial color="#1a1230" roughness={0.42} metalness={0.32} />
      </mesh>
      {/* Subtle tile grid — bank floor, not floating void */}
      <gridHelper args={[width - 1.2, 20, '#2a1860', '#1a0e38']} position={[0, 0.03, midZ]} />
      {/* Center aisle carpet runner */}
      <mesh position={[0, 0.025, midZ]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[2.4, depth - 1.2]} />
        <meshStandardMaterial color="#2a1040" roughness={0.85} metalness={0.08} />
      </mesh>
      <mesh position={[0, 0.028, midZ]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.08, depth - 1.2]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.35} toneMapped={false} />
      </mesh>
      {([-1.15, 1.15] as const).map((x) => (
        <mesh key={x} position={[x, 0.028, midZ]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.04, depth - 1.2]} />
          <meshBasicMaterial color="#f9c80e" transparent opacity={0.22} toneMapped={false} />
        </mesh>
      ))}

      {/* Back wall + wainscot (vault end) */}
      <mesh position={[0, ceilY / 2, zBack - wallT / 2]}>
        <boxGeometry args={[width + wallT * 2, ceilY, wallT]} />
        <meshStandardMaterial color={WALL} roughness={0.88} />
      </mesh>
      <mesh position={[0, 0.55, zBack + 0.02]}>
        <boxGeometry args={[width - 0.2, 1.15, 0.08]} />
        <meshStandardMaterial color={WAINSCOT} roughness={0.8} />
      </mesh>
      <mesh position={[0, 1.14, zBack + 0.06]}>
        <boxGeometry args={[width - 0.15, 0.045, 0.05]} />
        <meshStandardMaterial color={TRIM} metalness={0.45} roughness={0.35} />
      </mesh>
      <mesh position={[0, ceilY - 0.18, zBack + 0.08]}>
        <boxGeometry args={[width - 0.5, 0.04, 0.04]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>

      {/* Side walls — lit inward faces so the room reads from the aisle */}
      {([-1, 1] as const).map((side) => (
        <group key={side}>
          <mesh position={[side * (halfW + wallT / 2), ceilY / 2, midZ]}>
            <boxGeometry args={[wallT, ceilY, depth + wallT]} />
            <meshStandardMaterial color="#2a1a48" roughness={0.85} />
          </mesh>
          {/* Inner skin — brighter so FPV sees a solid wall, not void */}
          <mesh position={[side * (halfW - 0.02), ceilY / 2, midZ]}>
            <boxGeometry args={[0.06, ceilY - 0.2, depth - 0.4]} />
            <meshStandardMaterial color="#3a2860" roughness={0.7} metalness={0.12} />
          </mesh>
          <mesh position={[side * (halfW - 0.06), 0.55, midZ]}>
            <boxGeometry args={[0.12, 1.15, depth - 0.35]} />
            <meshStandardMaterial color="#243044" roughness={0.75} />
          </mesh>
          <mesh position={[side * (halfW - 0.08), 1.14, midZ]}>
            <boxGeometry args={[0.05, 0.05, depth - 0.5]} />
            <meshBasicMaterial color="#2de2e6" toneMapped={false} />
          </mesh>
          <mesh position={[side * (halfW - 0.08), ceilY - 0.25, midZ]}>
            <boxGeometry args={[0.04, 0.04, depth - 0.6]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
          {sconceZ.map((z, i) => (
            <group key={z} position={[side * (halfW - 0.22), 2.35, z]}>
              <mesh>
                <boxGeometry args={[0.1, 0.24, 0.14]} />
                <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
              </mesh>
              <mesh position={[side * -0.08, 0, 0]}>
                <sphereGeometry args={[0.07, 10, 10]} />
                <meshBasicMaterial color={i % 2 === 0 ? '#7ef9ff' : '#f9c80e'} toneMapped={false} />
              </mesh>
              <pointLight
                position={[side * -0.35, 0, 0]}
                intensity={0.55}
                color={i % 2 === 0 ? '#7ef9ff' : '#ffe0a0'}
                distance={5.5}
              />
            </group>
          ))}
          {/* Framed wall panels between sconces */}
          {[-3.5, 0.2, 3.2].map((z) => (
            <mesh key={`panel-${z}`} position={[side * (halfW - 0.12), 2.5, z]}>
              <boxGeometry args={[0.05, 1.4, 1.6]} />
              <meshStandardMaterial color="#221838" roughness={0.65} metalness={0.2} />
            </mesh>
          ))}
        </group>
      ))}

      {/* Front wall with portal */}
      <mesh position={[-(portalW / 2 + sidePanelW / 2), ceilY / 2, zFront]}>
        <boxGeometry args={[sidePanelW, ceilY, wallT]} />
        <meshStandardMaterial color={WALL} roughness={0.88} />
      </mesh>
      <mesh position={[portalW / 2 + sidePanelW / 2, ceilY / 2, zFront]}>
        <boxGeometry args={[sidePanelW, ceilY, wallT]} />
        <meshStandardMaterial color={WALL} roughness={0.88} />
      </mesh>
      <mesh position={[0, ceilY - 0.55, zFront]}>
        <boxGeometry args={[portalW + 0.35, 1.1, wallT + 0.04]} />
        <meshStandardMaterial color={WALL} roughness={0.85} />
      </mesh>
      <mesh position={[0, ceilY - 1.05, zFront + 0.02]}>
        <boxGeometry args={[portalW + 0.5, 0.08, 0.06]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
      </mesh>
      <mesh position={[0, ceilY - 1.12, zFront + 0.04]}>
        <boxGeometry args={[portalW + 0.35, 0.035, 0.04]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[side * (portalW / 2 + 0.06), 1.7, zFront + 0.02]}>
          <boxGeometry args={[0.12, 3.4, 0.1]} />
          <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
        </mesh>
      ))}

      {/* Ceiling — visible underside from eye height */}
      <mesh position={[0, ceilY + 0.08, midZ]}>
        <boxGeometry args={[width + wallT * 2, 0.22, depth + wallT]} />
        <meshStandardMaterial color="#1a1030" roughness={0.9} />
      </mesh>
      <mesh position={[0, ceilY - 0.02, midZ]} rotation={[Math.PI, 0, 0]}>
        <planeGeometry args={[width - 0.4, depth - 0.4]} />
        <meshStandardMaterial color="#241848" roughness={0.85} side={DoubleSide} />
      </mesh>
      {/* Short soft tubes — long bright bars bloomed into floating cyan slabs. */}
      {[-2.4, 2.4].map((x) => (
        <group key={x}>
          <mesh position={[x, ceilY - 0.08, midZ * 0.2]}>
            <boxGeometry args={[0.16, 0.12, depth * 0.55]} />
            <meshStandardMaterial color="#1a1428" roughness={0.7} metalness={0.2} />
          </mesh>
          <mesh position={[x, ceilY - 0.15, midZ * 0.05]}>
            <boxGeometry args={[0.2, 0.03, depth * 0.42]} />
            <meshStandardMaterial color="#7ec8d8" emissive="#2de2e6" emissiveIntensity={0.35} toneMapped={false} />
          </mesh>
        </group>
      ))}
      {[-5.6, -1.0, 2.4].map((z) => (
        <mesh key={z} position={[0, ceilY - 0.1, z]}>
          <boxGeometry args={[width - 0.8, 0.1, 0.14]} />
          <meshStandardMaterial color="#1a1428" roughness={0.7} metalness={0.2} />
        </mesh>
      ))}
      <mesh position={[0, ceilY - 0.05, zBack + 0.3]}>
        <boxGeometry args={[width - 0.6, 0.12, 0.2]} />
        <meshStandardMaterial color={TRIM} metalness={0.4} roughness={0.4} />
      </mesh>

      <Column x={-halfW + 0.45} z={zBack + 0.7} />
      <Column x={halfW - 0.45} z={zBack + 0.7} />
      <Column x={-halfW + 0.45} z={-1.2} />
      <Column x={halfW - 0.45} z={-1.2} />
      <Column x={-halfW + 0.45} z={zFront - 0.7} />
      <Column x={halfW - 0.45} z={zFront - 0.7} />

      {/* Writing ledge / deposit slip counters along the sides */}
      {([-1, 1] as const).map((side) => (
        <group key={`ledge-${side}`} position={[side * (halfW - 1.35), 0, zFront - 2.6]}>
          <mesh position={[0, 0.92, 0]}>
            <boxGeometry args={[1.1, 0.06, 0.55]} />
            <meshStandardMaterial color="#c8c0b0" roughness={0.35} metalness={0.15} />
          </mesh>
          <mesh position={[0, 0.45, 0]}>
            <boxGeometry args={[1.0, 0.85, 0.4]} />
            <meshStandardMaterial color="#1a1428" roughness={0.7} />
          </mesh>
          <mesh position={[0, 0.98, 0.1]}>
            <boxGeometry args={[0.35, 0.02, 0.25]} />
            <meshStandardMaterial color="#f4f0e4" roughness={0.9} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

/** Sparse drifting motes — kept tiny so they don't read as floor clutter. */
function DataMotes() {
  const ref = useRef<Group>(null)
  const motes = useMemo(
    () =>
      Array.from({ length: 6 }, (_, i) => ({
        x: ((i * 47) % 100) / 100 * 5 - 2.5,
        z: ((i * 31) % 100) / 100 * 4 - 2.5,
        phase: i * 0.9,
        speed: 0.22 + (i % 3) * 0.05,
        color: BEAM_COLORS[i % BEAM_COLORS.length],
      })),
    [],
  )
  useFrame(({ clock }) => {
    if (!ref.current) return
    const t = clock.getElapsedTime()
    ref.current.children.forEach((child, i) => {
      const m = motes[i]
      child.position.y = 1.6 + ((t * m.speed + m.phase) % 2.4)
      child.rotation.y = t * 0.5 + m.phase
    })
  })
  return (
    <group ref={ref}>
      {motes.map((m, i) => (
        <mesh key={i} position={[m.x, 1.8, m.z]}>
          <boxGeometry args={[0.04, 0.04, 0.04]} />
          <meshBasicMaterial color={m.color} transparent opacity={0.4} toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

function Warden() {
  return (
    <group position={[1.85, 0.05, Z_BACK + 1.85]} rotation={[0, Math.PI * 0.92, 0]} scale={0.88}>
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

function FloorGlowPaths({ tellers }: { tellers: (BotRow | null)[] }) {
  return (
    <group>
      {tellers.map((bot, i) => {
        const pose = slotPose(i)
        // Tick from aisle center toward each bay mouth.
        return (
          <mesh
            key={bot?.id || i}
            position={[pose.side * 0.45, 0.013, pose.z]}
            rotation={[-Math.PI / 2, 0, Math.PI / 2]}
          >
            <planeGeometry args={[0.05, 0.85]} />
            <meshBasicMaterial
              color={beamColorFor(bot?.id, i)}
              transparent
              opacity={0.38}
              depthWrite={false}
              toneMapped={false}
            />
          </mesh>
        )
      })}
    </group>
  )
}

function LaneFloorGuide({ color }: { color: string }) {
  const len = LANE_Z_MOUTH - 0.12
  const midZ = (LANE_Z_MOUTH + 0.12) / 2
  return (
    <group>
      <mesh position={[0, 0.014, midZ]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[LANE_HALF * 1.5, len]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.016, midZ]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.07, len]} />
        <meshBasicMaterial color={color} transparent opacity={0.5} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.018, LANE_Z_MOUTH + 0.06]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.3, 0.44, 24]} />
        <meshBasicMaterial color={color} transparent opacity={0.65} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  )
}

function RopeSpan({ x, z0, z1, color }: { x: number; z0: number; z1: number; color: string }) {
  const len = Math.abs(z1 - z0)
  const midZ = (z0 + z1) / 2
  return (
    <group>
      <mesh position={[x, ROPE_Y - 0.02, midZ]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.016, 0.016, len, 6]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <mesh position={[x, ROPE_Y - 0.02, midZ]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.028, 0.028, len * 0.98, 6]} />
        <meshBasicMaterial color={color} transparent opacity={0.22} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  )
}

/**
 * Full colored queue channel — aisle mouth to desk, open entry (no front gate bar).
 */
function QueueLane({ color }: { color: string }) {
  return (
    <group>
      <LaneFloorGuide color={color} />
      {([-LANE_HALF, LANE_HALF] as const).map((x) => (
        <group key={x}>
          <Stanchion position={[x, 0, LANE_Z_BACK]} color={color} />
          <Stanchion position={[x, 0, LANE_Z_MID]} color={color} />
          <Stanchion position={[x, 0, LANE_Z_MOUTH]} color={color} />
          <RopeSpan x={x} z0={LANE_Z_BACK} z1={LANE_Z_MID} color={color} />
          <RopeSpan x={x} z0={LANE_Z_MID} z1={LANE_Z_MOUTH} color={color} />
        </group>
      ))}
    </group>
  )
}

function CompliancePillar() {
  // Portal corners — clear of the T aisle.
  return (
    <group position={[-HALL_W / 2 + 0.95, 0, Z_FRONT - 1.15]}>
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
    <group position={[HALL_W / 2 - 0.95, 0.95, Z_FRONT - 1.15]} rotation={[0, -0.9, 0]}>
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
  // Portal alcoves — outside the teller banks.
  return (
    <group position={[x, 0, Z_FRONT - 1.35]}>
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
        <cylinderGeometry args={[0.034, 0.04, 0.84, 8]} />
        <meshStandardMaterial color="#1a1424" metalness={0.45} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.78, 0]}>
        <cylinderGeometry args={[0.042, 0.038, 0.07, 8]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <mesh position={[0, ROPE_Y + 0.05, 0]}>
        <sphereGeometry args={[0.058, 10, 10]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} emissive={color} emissiveIntensity={0.35} />
      </mesh>
      <mesh position={[0, 0.04, 0]}>
        <cylinderGeometry args={[0.1, 0.12, 0.05, 8]} />
        <meshStandardMaterial color="#121018" roughness={0.55} />
      </mesh>
    </group>
  )
}

/** Interior APEX-CITY TRUST — enclosed hall with grounded free-walk player. */
export function BankScene({ bots, desk, onSelectTeller, onOpenDeskOps, onWalkHint }: Props) {
  const tellers = useMemo(() => tellerSlots(bots), [bots])
  const workers = workersOnShift(bots)
  const [focus, setFocus] = useState(0)
  const [awayIndex, setAwayIndex] = useState<number | null>(null)
  const [recalling, setRecalling] = useState(false)
  const recallTimer = useRef<number | null>(null)

  const tellerMouths = useMemo(
    () =>
      tellers.map((bot, i) => {
        const pose = slotPose(i)
        return {
          x: pose.x + Math.sin(pose.rotY) * LANE_Z_MOUTH,
          z: pose.z + Math.cos(pose.rotY) * LANE_Z_MOUTH,
          id: bot?.id ?? null,
          index: i,
        }
      }),
    [tellers],
  )

  const presentIndexes = useMemo(
    () => tellers.map((b, i) => (b && b.present !== false ? i : -1)).filter((i) => i >= 0),
    [tellers],
  )

  useEffect(() => {
    if (!presentIndexes.length) {
      setAwayIndex(null)
      return
    }
    const pick = () => {
      setRecalling(false)
      setAwayIndex(presentIndexes[Math.floor(Math.random() * presentIndexes.length)] ?? null)
    }
    pick()
    const id = window.setInterval(pick, 14000)
    return () => window.clearInterval(id)
  }, [presentIndexes])

  const requestTeller = (id: string, index: number) => {
    if (awayIndex === index && !recalling) {
      setRecalling(true)
      if (recallTimer.current != null) window.clearTimeout(recallTimer.current)
      recallTimer.current = window.setTimeout(() => {
        setAwayIndex(null)
        setRecalling(false)
        onSelectTeller(id)
      }, 900)
      return
    }
    onSelectTeller(id)
  }

  useEffect(() => {
    return () => {
      if (recallTimer.current != null) window.clearTimeout(recallTimer.current)
    }
  }, [])

  return (
    <>
      <color attach="background" args={['#1a1030']} />
      <fog attach="fog" args={['#241848', 22, 55]} />
      <PerspectiveCamera makeDefault fov={62} near={0.05} far={90} position={HOME_POS} />

      <PlayerBot
        active
        hallHalfW={HALL_W / 2}
        zBack={Z_BACK}
        zFront={Z_FRONT}
        tellerMouths={tellerMouths}
        onInteract={(id, index) => {
          setFocus(index)
          requestTeller(id, index)
        }}
        onHintChange={onWalkHint}
      />

      <ambientLight intensity={0.62} color="#d0c4ff" />
      <directionalLight position={[2.8, 6.5, 2.2]} intensity={0.65} color="#ffe9c8" />
      <pointLight position={[0, 3.0, 0]} intensity={1.0} color="#fff0b0" distance={18} />
      <pointLight position={[0, 2.8, Z_BACK + 1.6]} intensity={0.55} color="#7ef9ff" distance={12} />
      <pointLight position={[-HALL_W / 2 + 1.2, 2.6, 0]} intensity={0.4} color="#b967ff" distance={8} />
      <pointLight position={[HALL_W / 2 - 1.2, 2.6, 0]} intensity={0.4} color="#b967ff" distance={8} />

      <BankEnclosure />
      {/* Service walls behind each teller bank — solid room shell, not void */}
      {([-1, 1] as const).map((side) => {
        const wallX = side * (AISLE_HALF + 1.85)
        const rowMidZ = TELLER_Z0 - ((SIDE_COUNT - 1) * TELLER_SPACING) / 2
        const rowLen = SIDE_COUNT * TELLER_SPACING + 2.2
        return (
          <group key={`svc-${side}`}>
            <mesh position={[wallX, HALL_HEIGHT / 2, rowMidZ]}>
              <boxGeometry args={[0.22, HALL_HEIGHT - 0.15, rowLen]} />
              <meshBasicMaterial color="#4a3278" toneMapped={false} />
            </mesh>
            <mesh position={[wallX - side * 0.12, 0.7, rowMidZ]}>
              <boxGeometry args={[0.08, 1.35, rowLen - 0.2]} />
              <meshBasicMaterial color="#2a3848" toneMapped={false} />
            </mesh>
            <mesh position={[wallX - side * 0.14, 1.4, rowMidZ]}>
              <boxGeometry args={[0.05, 0.06, rowLen - 0.3]} />
              <meshBasicMaterial color="#2de2e6" toneMapped={false} />
            </mesh>
            <mesh position={[wallX - side * 0.14, HALL_HEIGHT - 0.35, rowMidZ]}>
              <boxGeometry args={[0.05, 0.05, rowLen - 0.3]} />
              <meshBasicMaterial color="#f9c80e" toneMapped={false} />
            </mesh>
          </group>
        )
      })}
      {/* Ceiling plane — same bright purple family as service walls so FPV reads enclosure */}
      <mesh position={[0, HALL_HEIGHT - 0.08, TELLER_Z0 - ((SIDE_COUNT - 1) * TELLER_SPACING) / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[HALL_W - 0.6, SIDE_COUNT * TELLER_SPACING + 4]} />
        <meshBasicMaterial color="#4a3278" toneMapped={false} side={DoubleSide} />
      </mesh>
      <mesh position={[0, HALL_HEIGHT - 0.12, TELLER_Z0 - ((SIDE_COUNT - 1) * TELLER_SPACING) / 2]}>
        <boxGeometry args={[0.12, 0.06, SIDE_COUNT * TELLER_SPACING + 3.5]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <FloorGlowPaths tellers={tellers} />

      <HeroVaultDoor />
      <ProfitBoard desk={desk} />
      <LockboxWall bots={bots} />
      <CountingCage />
      <SideScreen side={-1} desk={desk} bots={bots} onOpen={onOpenDeskOps} />
      <SideScreen side={1} desk={desk} bots={bots} onOpen={onOpenDeskOps} />
      <TrustSeal workers={workers} />
      <Warden />
      <CompliancePillar />
      <NightDeposit />
      <WaitingBench x={-HALL_W / 2 + 2.2} />
      <WaitingBench x={HALL_W / 2 - 2.2} />
      <DataMotes />

      {tellers.map((bot, i) => {
        const pose = slotPose(i)
        const color = beamColorFor(bot?.id, i)
        return (
          <group key={bot?.id || `empty-${i}`} position={[pose.x, 0, pose.z]} rotation={[0, pose.rotY, 0]}>
            <TellerPod
              bot={bot}
              index={i}
              focused={focus === i}
              away={awayIndex === i}
              recalling={recalling && awayIndex === i}
              onSelect={(id) => {
                setFocus(i)
                requestTeller(id, i)
              }}
            />
            <QueueLane color={color} />
          </group>
        )
      })}

      <NeonBloom strength={0.12} />
    </>
  )
}
