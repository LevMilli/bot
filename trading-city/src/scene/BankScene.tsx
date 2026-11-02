import { useEffect, useMemo, useRef, useState } from 'react'
import { Html, OrbitControls, PerspectiveCamera } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { DoubleSide, MathUtils, type Group, type Mesh } from 'three'
import type { BotRow, Desk } from '../types'
import { BEAM_COLORS, beamColorFor, money, workersOnShift } from '../data/format'
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

type Props = {
  bots: BotRow[]
  desk?: Desk
  onSelectTeller: (id: string) => void
  /** Open the 2D desk ops board (budgets / adapt / fill tax) from a ledger click. */
  onOpenDeskOps?: () => void
}

/** Office-matched synthwave trust hall — purple shell, cyan trim, amber chrome. */
const WALL = '#241848'
const WALL_DEEP = '#160e2c'
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
const AISLE_HALF = 3.25
/** Frontmost row (toward portal); rows step toward the vault (−Z). */
const TELLER_Z0 = 2.35
/** Bigger enclosed hall so zoom-out does not clip into black fog. */
const HALL_W = 18.5
const Z_BACK = -11.5
const Z_FRONT = 8.2
const HALL_HEIGHT = 5.4
const HOME_POS: [number, number, number] = [0, 3.05, 6.4]
const HOME_TARGET: [number, number, number] = [0, 1.45, -2.8]
/** Half-width of each teller's private rope channel (local X). */
const LANE_HALF = 0.7
/** Mouth posts into the aisle (local +Z) — open entry, no front bar. */
const LANE_Z_MOUTH = 1.85
const LANE_Z_MID = 1.15
const LANE_Z_BACK = 0.55
const ROPE_Y = 0.82
const ZOOM_DIST_NEAR = 3.55
const ZOOM_DIST_MAX = 22

type SlotPose = {
  side: -1 | 1
  row: number
  x: number
  z: number
  rotY: number
}

/**
 * Left = 0..5, right = 6..11.
 * Local +Z = customer approach toward the aisle.
 * Left rotY=+π/2 → local +Z maps to world +X (into the path).
 * Right rotY=−π/2 → local +Z maps to world −X.
 * Bot sits at local −Z (wall side); ropes extend local +Z (inside / aisle).
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
  // Whole station (desk, glass, lamp, plate, lane cues) follows the building beam color.
  // Parent group orients local +Z toward the center aisle.
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
    // Step into the aisle (local +Z) when away; walk back when recalled.
    const targetZ = recalling ? 0 : away ? 1.05 : 0
    const targetX = recalling ? 0 : away ? (index % 2 === 0 ? -0.55 : 0.55) : 0
    walk.current.z = MathUtils.damp(walk.current.z, targetZ, 5.5, dt)
    walk.current.x = MathUtils.damp(walk.current.x, targetX, 5.5, dt)
    if (botRoot.current) {
      botRoot.current.position.x = walk.current.x
      botRoot.current.position.z = -0.38 + walk.current.z
      // Face the aisle customer (local +Z). Back-plate is local +Z → Y=π.
      botRoot.current.rotation.y = Math.PI
    }
  })

  const select = (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    if (bot) onSelect(bot.id)
  }

  const podW = 1.52

  return (
    <group position={[0, 0, -0.05]}>
      {/* Station body — subtle emissive wash in building color */}
      <mesh position={[0, 0.42, -0.15]}>
        <boxGeometry args={[podW, 0.84, 0.7]} />
        <meshStandardMaterial
          color="#14101c"
          roughness={0.72}
          metalness={0.22}
          emissive={color}
          emissiveIntensity={offline ? 0.04 : focused ? 0.14 : 0.08}
        />
      </mesh>
      <mesh position={[0, 0.86, 0.18]} castShadow>
        <boxGeometry args={[podW + 0.06, 0.08, 0.95]} />
        <meshStandardMaterial color="#d8d0c0" roughness={0.28} metalness={0.22} />
      </mesh>
      {/* Thin side pinstripes — full neon slabs read as floating colored cubes. */}
      {([-podW / 2 - 0.015, podW / 2 + 0.015] as const).map((sx) => (
        <mesh key={sx} position={[sx, 0.55, -0.15]}>
          <boxGeometry args={[0.02, 0.55, 0.55]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.35} toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0, 0.87, 0.66]}>
        <boxGeometry args={[podW * 0.5, 0.026, 0.035]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} emissive={color} emissiveIntensity={focused ? 0.35 : 0.16} />
      </mesh>
      <mesh position={[0, 0.1, 0.22]}>
        <boxGeometry args={[podW * 0.7, 0.04, 0.025]} />
        <meshStandardMaterial color={BRASS} metalness={0.7} roughness={0.3} emissive={color} emissiveIntensity={0.2} />
      </mesh>

      {/* Soft glass fins */}
      {([-0.74, 0.74] as const).map((sx) => (
        <group key={sx}>
          <mesh position={[sx, 1.4, -0.05]}>
            <boxGeometry args={[0.03, 1.0, 0.55]} />
            <meshStandardMaterial color="#7ef9ff" transparent opacity={0.06} metalness={0.3} roughness={0.15} depthWrite={false} />
          </mesh>
          <mesh position={[sx, 1.95, -0.05]}>
            <boxGeometry args={[0.04, 0.04, 0.58]} />
            <meshStandardMaterial color={BRASS} metalness={0.7} roughness={0.28} emissive={color} emissiveIntensity={0.2} />
          </mesh>
        </group>
      ))}

      {/* desk terminal + lamp */}
      <mesh position={[-0.38, 1.05, 0.28]} rotation={[-0.4, 0.12, 0]}>
        <boxGeometry args={[0.42, 0.28, 0.03]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} emissive={color} emissiveIntensity={0.12} />
      </mesh>
      <mesh position={[-0.38, 1.05, 0.3]} rotation={[-0.4, 0.12, 0]}>
        <planeGeometry args={[0.36, 0.22]} />
        <meshBasicMaterial color={offline ? '#2a1830' : color} transparent opacity={0.55} toneMapped={false} />
      </mesh>
      <mesh position={[0.48, 0.95, 0.15]}>
        <cylinderGeometry args={[0.03, 0.04, 0.08, 10]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh position={[0.48, 1.12, 0.15]}>
        <cylinderGeometry args={[0.01, 0.01, 0.22, 8]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh ref={lamp} position={[0.48, 1.24, 0.26]} rotation={[0.55, 0, 0]}>
        <coneGeometry args={[0.08, 0.11, 12, 1, true]} />
        <meshStandardMaterial
          color="#1a1420"
          emissive={offline ? '#401820' : color}
          emissiveIntensity={0.7}
          side={DoubleSide}
          roughness={0.4}
        />
      </mesh>

      {/* Sharp canvas nameplate — thin accent rim only (solid color plates looked like floating bars). */}
      <mesh
        position={[0, 1.88, 0.42]}
        onClick={select}
        onPointerOver={() => bot && (document.body.style.cursor = 'pointer')}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[1.38, 0.5, 0.05]} />
        <meshStandardMaterial color={INK} metalness={0.35} roughness={0.4} emissive={color} emissiveIntensity={focused ? 0.28 : 0.1} />
      </mesh>
      <mesh position={[0, 1.88, 0.455]} onClick={select}>
        <planeGeometry args={[1.28, 0.42]} />
        <meshBasicMaterial map={plate} toneMapped={false} />
      </mesh>
      <mesh position={[0, 2.14, 0.44]}>
        <boxGeometry args={[1.4, 0.035, 0.03]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.62, 0.44]}>
        <boxGeometry args={[1.4, 0.03, 0.03]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>

      {/* standing teller facing the customer (+Z / camera) */}
      <group ref={botRoot} position={[0, 0.02, -0.38]} rotation={[0, Math.PI, 0]} scale={0.88}>
        <BotFigure pose={away && !recalling ? 'waiting' : pose} seated={false} />
      </group>

      {/* Approach halo at the rope mouth */}
      <mesh
        ref={halo}
        position={[0, 0.021, LANE_Z_MOUTH + 0.06]}
        rotation={[-Math.PI / 2, 0, 0]}
        onClick={select}
        onPointerOver={() => bot && (document.body.style.cursor = 'pointer')}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <ringGeometry args={[focused ? 0.4 : 0.46, focused ? 0.68 : 0.6, 32]} />
        <meshBasicMaterial color={color} transparent opacity={focused ? 0.9 : 0.65} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.016, LANE_Z_MOUTH + 0.06]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.38, 28]} />
        <meshBasicMaterial color={color} transparent opacity={focused ? 0.26 : 0.12} />
      </mesh>
      {away && !recalling && (
        <Html position={[0, 2.15, -0.2]} center distanceFactor={9} style={{ pointerEvents: 'none' }}>
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
    <group position={[side * 4.15, 2.85, Z_BACK + 0.58]}>
      <mesh
        onClick={open}
        onPointerOver={() => {
          document.body.style.cursor = onOpen ? 'pointer' : 'default'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[3.35, 1.55, 0.14]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} />
      </mesh>
      <mesh position={[0, 0, 0.08]} onClick={open}>
        <planeGeometry args={[3.1, 1.35]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.82, 0.06]}>
        <boxGeometry args={[3.4, 0.05, 0.06]} />
        <meshBasicMaterial color={accent} toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.82, 0.06]}>
        <boxGeometry args={[3.4, 0.04, 0.05]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      {onOpen && (
        <Html position={[0, -1.05, 0.1]} center distanceFactor={14} style={{ pointerEvents: 'none' }}>
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
  const wallT = 0.28
  const zBack = Z_BACK
  const zFront = Z_FRONT
  const depth = zFront - zBack
  const midZ = (zFront + zBack) / 2
  const portalW = 4.4
  const sidePanelW = (width - portalW) / 2
  const sconceZ = [zBack + 2.4, -1.0, zFront - 2.2]
  const ceilY = HALL_HEIGHT

  return (
    <group>
      {/* Thick floor slab */}
      <mesh position={[0, -0.08, midZ]} receiveShadow>
        <boxGeometry args={[width + 0.4, 0.18, depth + 0.4]} />
        <meshStandardMaterial color={FLOOR} roughness={0.55} metalness={0.28} />
      </mesh>
      <mesh position={[0, 0.01, midZ]} receiveShadow>
        <boxGeometry args={[width - 0.35, 0.04, depth - 0.5]} />
        <meshStandardMaterial color="#160e2c" roughness={0.4} metalness={0.35} />
      </mesh>
      <gridHelper args={[Math.min(width - 1.2, 16), 28, '#2de2e6', '#2a1060']} position={[0, 0.035, midZ * 0.15]} />

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

      {/* Side walls */}
      {([-1, 1] as const).map((side) => (
        <group key={side}>
          <mesh position={[side * (halfW + wallT / 2), ceilY / 2, midZ]}>
            <boxGeometry args={[wallT, ceilY, depth + wallT]} />
            <meshStandardMaterial color={WALL_DEEP} roughness={0.9} />
          </mesh>
          <mesh position={[side * (halfW - 0.04), 0.55, midZ]}>
            <boxGeometry args={[0.1, 1.15, depth - 0.3]} />
            <meshStandardMaterial color={WAINSCOT} roughness={0.8} />
          </mesh>
          {sconceZ.filter((_, i) => i % 2 === 0).map((z) => (
            <group key={z} position={[side * (halfW - 0.18), 2.55, z]}>
              <mesh>
                <boxGeometry args={[0.08, 0.22, 0.12]} />
                <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
              </mesh>
              <mesh position={[side * -0.06, 0, 0]}>
                <sphereGeometry args={[0.06, 10, 10]} />
                <meshBasicMaterial color="#7ef9ff" toneMapped={false} />
              </mesh>
              <pointLight position={[side * -0.2, 0, 0]} intensity={0.22} color="#7ef9ff" distance={4.2} />
            </group>
          ))}
          {sconceZ.filter((_, i) => i % 2 === 1).map((z) => (
            <mesh key={z} position={[side * (halfW - 0.16), 2.35, z]}>
              <boxGeometry args={[0.04, 1.55, 1.0]} />
              <meshStandardMaterial color="#1c1430" roughness={0.75} metalness={0.15} />
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

      {/* Ceiling slab + the old coffered tubes, run the length of the hall */}
      <mesh position={[0, ceilY + 0.08, midZ]}>
        <boxGeometry args={[width + wallT * 2, 0.22, depth + wallT]} />
        <meshStandardMaterial color="#100a1e" roughness={0.95} />
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

      <Column x={-halfW + 0.35} z={zBack + 0.55} />
      <Column x={halfW - 0.35} z={zBack + 0.55} />
      <Column x={-halfW + 0.35} z={zFront - 0.55} />
      <Column x={halfW - 0.35} z={zFront - 0.55} />

      {/* Clear center aisle to the vault */}
      <mesh position={[0, 0.018, midZ * 0.2]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.45, depth * 0.72]} />
        <meshStandardMaterial color="#1a0e28" roughness={0.45} metalness={0.4} />
      </mesh>
      <mesh position={[0, 0.022, midZ * 0.2]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.09, depth * 0.72]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.42} toneMapped={false} />
      </mesh>
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

/** Interior APEX-CITY TRUST — detailed hall, tellers wrapped around a square. */
export function BankScene({ bots, desk, onSelectTeller, onOpenDeskOps }: Props) {
  const controls = useRef<OrbitControlsImpl>(null)
  // One detailed station per building, walked around the square.
  const tellers = useMemo(() => tellerSlots(bots), [bots])
  const workers = workersOnShift(bots)
  const startFocus = 0
  const [focus, setFocus] = useState(startFocus)
  const [awayIndex, setAwayIndex] = useState<number | null>(null)
  const [recalling, setRecalling] = useState(false)
  const recallTimer = useRef<number | null>(null)
  /** Brief A/D framing only — released after settle or on drag/zoom. */
  const snapRef = useRef<{ active: boolean; focus: number }>({ active: false, focus: startFocus })

  const presentIndexes = useMemo(
    () => tellers.map((b, i) => (b && b.present !== false ? i : -1)).filter((i) => i >= 0),
    [tellers],
  )

  const releaseCameraLock = () => {
    snapRef.current.active = false
  }

  const beginFocusSnap = (index: number) => {
    snapRef.current = { active: true, focus: index }
  }

  useEffect(() => {
    const orbit = controls.current
    const cam = orbit?.object
    if (!orbit || !cam) return
    cam.position.set(...HOME_POS)
    orbit.target.set(...HOME_TARGET)
    orbit.update()
    snapRef.current = { active: false, focus: startFocus }
  }, [])

  // Cycle one present teller stepping away — light life without extra lights.
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

  // A/D · ←/→ briefly snap to teller; W/S · ↑/↓ free-roam dolly; Enter / Space opens.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const key = e.key.toLowerCase()
      if (key === 'arrowleft' || key === 'a') {
        e.preventDefault()
        setFocus((f) => {
          const next = Math.max(0, f - 1)
          beginFocusSnap(next)
          return next
        })
      } else if (key === 'arrowright' || key === 'd') {
        e.preventDefault()
        setFocus((f) => {
          const next = Math.min(TOTAL_SLOTS - 1, f + 1)
          beginFocusSnap(next)
          return next
        })
      } else if (key === 'arrowup' || key === 'w' || key === 'arrowdown' || key === 's') {
        e.preventDefault()
        releaseCameraLock()
        const orbit = controls.current
        if (!orbit) return
        const cam = orbit.object
        const dx = cam.position.x - orbit.target.x
        const dy = cam.position.y - orbit.target.y
        const dz = cam.position.z - orbit.target.z
        const dist = Math.hypot(dx, dy, dz) || 1
        const pose = slotPose(focus)
        orbit.target.x = MathUtils.lerp(orbit.target.x, pose.x * 0.4, 0.18)
        orbit.target.z = MathUtils.lerp(orbit.target.z, pose.z, 0.18)
        const nx = dx / dist
        const ny = dy / dist
        const nz = dz / dist
        const step = key === 'arrowup' || key === 'w' ? -0.38 : 0.38
        const nextDist = MathUtils.clamp(dist + step, ZOOM_DIST_NEAR - 0.15, ZOOM_DIST_MAX)
        cam.position.set(
          orbit.target.x + nx * nextDist,
          orbit.target.y + ny * nextDist,
          orbit.target.z + nz * nextDist,
        )
        orbit.update()
      } else if (key === 'enter' || key === ' ') {
        const bot = tellers[focus]
        if (bot) {
          e.preventDefault()
          requestTeller(bot.id, focus)
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [tellers, focus, awayIndex, recalling])

  useFrame((_, dt) => {
    const orbit = controls.current
    if (!orbit) return
    orbit.minDistance = ZOOM_DIST_NEAR - 0.15
    orbit.maxDistance = ZOOM_DIST_MAX
    if (!snapRef.current.active) return

    const pose = slotPose(snapRef.current.focus)
    // Stand in the clear aisle and look at the teller face (ropes on the inside).
    const targetX = pose.x * 0.48
    const targetY = 1.32
    const targetZ = pose.z
    orbit.target.x = MathUtils.damp(orbit.target.x, targetX, 5.5, dt)
    orbit.target.y = MathUtils.damp(orbit.target.y, targetY, 5.5, dt)
    orbit.target.z = MathUtils.damp(orbit.target.z, targetZ, 5.5, dt)

    const cam = orbit.object
    const wantX = pose.side * 0.15
    const wantY = 2.35
    const wantZ = pose.z + 0.35
    cam.position.x = MathUtils.damp(cam.position.x, wantX, 5.2, dt)
    cam.position.y = MathUtils.damp(cam.position.y, wantY, 5.2, dt)
    cam.position.z = MathUtils.damp(cam.position.z, wantZ, 5.2, dt)

    const settled =
      Math.abs(cam.position.x - wantX) < 0.05 &&
      Math.abs(cam.position.z - wantZ) < 0.08 &&
      Math.abs(orbit.target.x - targetX) < 0.05
    if (settled) releaseCameraLock()
  })

  return (
    <>
      <color attach="background" args={['#12082a']} />
      <fog attach="fog" args={['#1a0a38', 22, 70]} />
      <PerspectiveCamera makeDefault fov={42} near={0.08} far={200} position={HOME_POS} />
      <OrbitControls
        ref={controls}
        makeDefault
        target={HOME_TARGET}
        enableDamping
        dampingFactor={0.08}
        enablePan={false}
        minDistance={ZOOM_DIST_NEAR - 0.15}
        maxDistance={ZOOM_DIST_MAX}
        minPolarAngle={0.7}
        maxPolarAngle={1.55}
        minAzimuthAngle={-2.6}
        maxAzimuthAngle={2.6}
        onStart={releaseCameraLock}
      />

      <ambientLight intensity={0.42} color="#c8b8ff" />
      <directionalLight position={[3.2, 7.2, 2.8]} intensity={0.55} color="#ffe9c8" />
      <pointLight position={[0, 3.4, -1.0]} intensity={0.85} color="#fff0b0" distance={14} />
      <pointLight position={[0, 3.1, Z_BACK + 1.8]} intensity={0.4} color="#7ef9ff" distance={8} />

      <BankEnclosure />
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
      <WaitingBench x={-4.35} />
      <WaitingBench x={4.35} />
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
                beginFocusSnap(i)
                requestTeller(id, i)
              }}
            />
            <QueueLane color={color} />
          </group>
        )
      })}

      <Html position={[0, 0.08, Z_FRONT - 0.35]} center distanceFactor={14} style={{ pointerEvents: 'none' }}>
        <div
          style={{
            fontFamily: 'Share Tech Mono, monospace',
            fontSize: '11px',
            color: '#9aa3c7',
            textAlign: 'center',
            letterSpacing: '0.06em',
          }}
        >
          A/D · ←→ snap · W/S · ↑↓ zoom free · Enter open · drag to look · cash {money(desk?.cash)}
        </div>
      </Html>

      {/* Light bloom — heavy bloom + long ceiling neon read as floating cyan slabs. */}
      <NeonBloom strength={0.16} />
    </>
  )
}
