import { useEffect, useMemo, useRef, useState } from 'react'
import { Html, PerspectiveCamera } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { CanvasTexture, DoubleSide, MathUtils, type Group, type Mesh, type MeshStandardMaterial, type PointLight } from 'three'
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
import { CityBotFigure } from './CityBotFigure'
import { PlayerBot } from './PlayerBot'
import type { FloorObstacle } from '../data/bankWalk'

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
const CYAN = '#2de2e6'
const GREEN = '#39ff14'

/**
 * Dual banks + clear center aisle to the vault.
 * Bots stand on the wall side; ropes sit on the aisle (inside); desks face the path.
 * Fixed 12 slots (6 left + 6 right).
 */
const SIDE_COUNT = 6
const TOTAL_SLOTS = SIDE_COUNT * 2
const TELLER_SPACING = 2.15
/** Desk origin distance from aisle centerline. */
const AISLE_HALF = 3.55
/** Frontmost row (toward portal); rows step toward the vault (−Z). */
const TELLER_Z0 = 2.55
/** Enclosed vault room — solid walls just outside the teller banks. */
const HALL_W = 13.6
const Z_BACK = -12.2
const Z_FRONT = 8.0
const HALL_HEIGHT = 5.1
const HOME_POS: [number, number, number] = [0, 1.85, 5.6]
/** Half-width of each teller's private rope channel (local X). */
const LANE_HALF = 0.55
/**
 * Queue ropes live entirely in the aisle — well forward of the counter lip.
 * Desk cabinet ends ≈ local Z −0.15; keep LANE_Z_BACK ≥ 1.35.
 */
const LANE_Z_MOUTH = 2.7
const LANE_Z_MID = 2.1
const LANE_Z_BACK = 1.55
const ROPE_Y = 0.82
/** Bot stands behind the cabinet (local −Z), clear of the desk body. */
const BOT_Z = -1.62
/** Desk collision half-depth from slot origin toward aisle / wall. */
const DESK_COLLIDE = { aisle: 0.35, wall: 1.05, halfW: 0.75 }

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
  near,
  away,
  recalling,
  onSelect,
}: {
  bot: BotRow | null
  index: number
  focused: boolean
  near: boolean
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
  const screen = useRef<Mesh>(null)
  const screenB = useRef<Mesh>(null)
  const pad = useRef<Mesh>(null)
  const botRoot = useRef<Group>(null)
  const walk = useRef({ z: 0, x: 0 })

  useEffect(() => () => plate.dispose(), [plate])
  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime()
    if (lamp.current) {
      const mat = lamp.current.material as { emissiveIntensity?: number }
      if (mat.emissiveIntensity != null) {
        mat.emissiveIntensity =
          offline ? 0.2 : (focused || near ? 0.95 : 0.55) + Math.sin(t * 2.4 + index) * 0.18
      }
    }
    if (halo.current) {
      const pulse = focused || near ? 0.1 : 0.035
      const s = 1 + Math.sin(t * (near ? 3.2 : 1.9) + index) * pulse
      halo.current.scale.set(s, 1, s)
      const mat = halo.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = near || focused ? 0.9 : 0.55
    }
    if (screen.current && !offline) {
      const mat = screen.current.material as { opacity?: number }
      if (mat.opacity != null) {
        mat.opacity = 0.45 + Math.sin(t * 5.5 + index * 1.7) * 0.12 + (near ? 0.12 : 0)
      }
    }
    if (screenB.current && !offline) {
      const mat = screenB.current.material as { opacity?: number }
      if (mat.opacity != null) {
        mat.opacity = 0.4 + Math.sin(t * 4.2 + index * 2.1) * 0.1 + (near ? 0.1 : 0)
      }
    }
    if (pad.current && !offline) {
      pad.current.position.y = 0.96 + Math.sin(t * 3.4 + index) * 0.004
    }
    // Step sideways behind the counter when away — never through the desk.
    const targetZ = recalling ? 0 : away ? 0.1 : 0
    const targetX = recalling ? 0 : away ? (index % 2 === 0 ? -0.62 : 0.62) : 0
    walk.current.z = MathUtils.damp(walk.current.z, targetZ, 5.5, dt)
    walk.current.x = MathUtils.damp(walk.current.x, targetX, 5.5, dt)
    if (botRoot.current) {
      botRoot.current.position.x = walk.current.x
      botRoot.current.position.y = 0.18 + (away && !recalling ? Math.sin(t * 6) * 0.02 : 0)
      botRoot.current.position.z = BOT_Z + walk.current.z
      // Idle lean toward the transaction pad when on duty.
      const workLean = !away && !offline && Math.sin(t * 0.55 + index) > 0.55 ? 0.12 : 0
      const face =
        away && !recalling
          ? Math.PI + (index % 2 === 0 ? -0.55 : 0.55)
          : Math.PI + workLean * (index % 2 === 0 ? -1 : 1)
      botRoot.current.rotation.y = MathUtils.damp(botRoot.current.rotation.y, face, 4.5, dt)
    }
  })

  const select = (e: { stopPropagation: () => void }) => {
    e.stopPropagation()
    if (bot) onSelect(bot.id)
  }

  const podW = 1.35

  return (
    <group>
      {/* Raised platform under the whole station */}
      <mesh position={[0, 0.04, -0.55]} receiveShadow>
        <boxGeometry args={[podW + 0.28, 0.08, 1.4]} />
        <meshStandardMaterial color="#14101c" roughness={0.75} metalness={0.15} />
      </mesh>
      <mesh position={[0, 0.09, -0.55]}>
        <boxGeometry args={[podW + 0.2, 0.02, 1.32]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.28} />
      </mesh>
      {/* Soft underglow */}
      <mesh position={[0, 0.02, -0.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[podW + 0.1, 1.1]} />
        <meshBasicMaterial color={color} transparent opacity={0.1} depthWrite={false} toneMapped={false} />
      </mesh>
      {/* Compact cabinet — wall side only; front face ≈ −0.22 */}
      <mesh position={[0, 0.5, -0.62]} castShadow>
        <boxGeometry args={[podW, 0.78, 0.55]} />
        <meshStandardMaterial
          color="#16121c"
          roughness={0.68}
          metalness={0.25}
          emissive={color}
          emissiveIntensity={offline ? 0.03 : focused ? 0.12 : 0.06}
        />
      </mesh>
      {/* Cash-drawer faces */}
      {[0.28, 0.48, 0.68].map((y) => (
        <mesh key={y} position={[0, y, -0.34]}>
          <boxGeometry args={[podW - 0.28, 0.12, 0.03]} />
          <meshStandardMaterial color="#2a2438" metalness={0.45} roughness={0.4} />
        </mesh>
      ))}
      {[0.28, 0.48, 0.68].map((y) => (
        <mesh key={`h-${y}`} position={[0.42, y, -0.32]}>
          <boxGeometry args={[0.1, 0.018, 0.02]} />
          <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
        </mesh>
      ))}
      {/* Front ticker fascia */}
      <mesh position={[0, 0.42, -0.33]}>
        <boxGeometry args={[podW - 0.4, 0.05, 0.02]} />
        <meshStandardMaterial color={CYAN} emissive={CYAN} emissiveIntensity={0.45} toneMapped={false} />
      </mesh>
      {/* Counter top — lip ≈ +0.05, clear of ropes at 1.4+ */}
      <mesh position={[0, 0.92, -0.42]} castShadow>
        <boxGeometry args={[podW + 0.1, 0.06, 0.78]} />
        <meshStandardMaterial color="#d8d0c0" roughness={0.28} metalness={0.22} />
      </mesh>
      {/* Glass transaction strip */}
      <mesh position={[0, 0.96, -0.28]}>
        <boxGeometry args={[podW * 0.7, 0.018, 0.35]} />
        <meshPhysicalMaterial
          color="#7ef9ff"
          metalness={0.05}
          roughness={0.08}
          transmission={0.5}
          transparent
          opacity={0.4}
          thickness={0.15}
        />
      </mesh>
      <mesh position={[0, 0.96, -0.05]}>
        <boxGeometry args={[podW * 0.55, 0.025, 0.03]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} emissive={color} emissiveIntensity={focused ? 0.3 : 0.14} />
      </mesh>
      {/* Transaction pad + keyboard */}
      <mesh ref={pad} position={[0.15, 0.96, -0.2]} rotation={[-Math.PI / 2, 0, 0.08]}>
        <planeGeometry args={[0.28, 0.2]} />
        <meshStandardMaterial color="#f4f0e4" roughness={0.9} emissive={color} emissiveIntensity={near ? 0.18 : 0.05} />
      </mesh>
      <mesh position={[-0.22, 0.955, -0.18]}>
        <boxGeometry args={[0.32, 0.02, 0.16]} />
        <meshStandardMaterial color="#121018" metalness={0.45} roughness={0.4} />
      </mesh>
      <mesh position={[-0.22, 0.97, -0.18]}>
        <boxGeometry args={[0.28, 0.008, 0.12]} />
        <meshStandardMaterial color={CYAN} emissive={CYAN} emissiveIntensity={0.22} toneMapped={false} />
      </mesh>
      {([-podW / 2 - 0.02, podW / 2 + 0.02] as const).map((sx) => (
        <group key={sx}>
          <mesh position={[sx, 0.55, -0.58]}>
            <boxGeometry args={[0.022, 0.7, 0.42]} />
            <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.28} toneMapped={false} />
          </mesh>
          <mesh position={[sx, 0.92, -0.58]}>
            <boxGeometry args={[0.04, 0.04, 0.45]} />
            <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
          </mesh>
        </group>
      ))}

      {([-0.7, 0.7] as const).map((sx) => (
        <group key={sx}>
          <mesh position={[sx, 1.35, -0.55]}>
            <boxGeometry args={[0.024, 0.7, 0.35]} />
            <meshStandardMaterial color="#7ef9ff" transparent opacity={0.1} metalness={0.3} roughness={0.15} depthWrite={false} />
          </mesh>
          <mesh position={[sx, 1.72, -0.55]}>
            <boxGeometry args={[0.032, 0.032, 0.38]} />
            <meshStandardMaterial color={BRASS} metalness={0.7} roughness={0.28} />
          </mesh>
        </group>
      ))}

      {/* Dual terminals */}
      <mesh position={[-0.28, 1.05, -0.22]} rotation={[-0.32, 0.08, 0]}>
        <boxGeometry args={[0.34, 0.22, 0.028]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} emissive={color} emissiveIntensity={0.12} />
      </mesh>
      <mesh ref={screen} position={[-0.28, 1.05, -0.2]} rotation={[-0.32, 0.08, 0]}>
        <planeGeometry args={[0.28, 0.16]} />
        <meshBasicMaterial color={offline ? '#2a1830' : color} transparent opacity={0.55} toneMapped={false} />
      </mesh>
      <mesh position={[0.22, 1.0, -0.28]} rotation={[-0.28, -0.12, 0]}>
        <boxGeometry args={[0.26, 0.16, 0.024]} />
        <meshStandardMaterial color={INK} metalness={0.45} roughness={0.32} emissive={GREEN} emissiveIntensity={0.08} />
      </mesh>
      <mesh ref={screenB} position={[0.22, 1.0, -0.26]} rotation={[-0.28, -0.12, 0]}>
        <planeGeometry args={[0.2, 0.11]} />
        <meshBasicMaterial color={offline ? '#1a2020' : GREEN} transparent opacity={0.45} toneMapped={false} />
      </mesh>
      <mesh position={[0.36, 0.97, -0.32]}>
        <cylinderGeometry args={[0.026, 0.034, 0.06, 10]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh position={[0.36, 1.1, -0.32]}>
        <cylinderGeometry args={[0.008, 0.008, 0.16, 8]} />
        <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh ref={lamp} position={[0.36, 1.18, -0.22]} rotation={[0.4, 0, 0]}>
        <coneGeometry args={[0.065, 0.085, 12, 1, true]} />
        <meshStandardMaterial
          color="#1a1420"
          emissive={offline ? '#401820' : color}
          emissiveIntensity={0.7}
          side={DoubleSide}
          roughness={0.4}
        />
      </mesh>
      <pointLight position={[0.2, 1.15, -0.1]} intensity={0.28} color="#fff4d0" distance={2.4} />

      {/* Nameplate on a post above the cabinet — not floating into the bot */}
      <mesh position={[0, 1.25, -0.78]}>
        <boxGeometry args={[0.05, 0.55, 0.05]} />
        <meshStandardMaterial color="#2a2438" metalness={0.5} roughness={0.35} />
      </mesh>
      <mesh
        position={[0, 1.62, -0.72]}
        onClick={select}
        onPointerOver={() => bot && (document.body.style.cursor = 'pointer')}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[1.18, 0.4, 0.05]} />
        <meshStandardMaterial color={INK} metalness={0.35} roughness={0.4} emissive={color} emissiveIntensity={focused ? 0.28 : 0.1} />
      </mesh>
      <mesh position={[0, 1.62, -0.69]} onClick={select}>
        <planeGeometry args={[1.08, 0.32]} />
        <meshBasicMaterial map={plate} toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.83, -0.7]}>
        <boxGeometry args={[1.2, 0.025, 0.025]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      {/* Window number badge */}
      <mesh position={[podW / 2 - 0.12, 1.05, -0.33]}>
        <boxGeometry args={[0.22, 0.16, 0.03]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.45} toneMapped={false} />
      </mesh>

      {/* Teller behind the cabinet — standing height, clear of the desk body */}
      <group ref={botRoot} position={[0, 0.18, BOT_Z]} rotation={[0, Math.PI, 0]} scale={0.9}>
        <CityBotFigure
          context="bank"
          pose={away && !recalling ? 'waiting' : pose}
          seated={false}
          seed={index}
          unitMark={String(index + 1).padStart(2, '0')}
        />
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
        <ringGeometry args={[focused || near ? 0.34 : 0.42, focused || near ? 0.62 : 0.54, 28]} />
        <meshBasicMaterial color={color} transparent opacity={focused || near ? 0.9 : 0.55} toneMapped={false} />
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
  return (
    <group position={[0, 3.55, Z_BACK + 0.55]}>
      <mesh>
        <boxGeometry args={[5.6, 1.0, 0.14]} />
        <meshStandardMaterial color={INK} metalness={0.5} roughness={0.28} />
      </mesh>
      <mesh position={[0, 0, 0.08]}>
        <planeGeometry args={[5.25, 0.82]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.54, 0.05]}>
        <boxGeometry args={[5.7, 0.04, 0.07]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.54, 0.05]}>
        <boxGeometry args={[5.7, 0.04, 0.07]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
      </mesh>
    </group>
  )
}

/** Hero circular vault door — layered steel, rotating rings, chamber glow. */
function HeroVaultDoor() {
  const dial = useRef<Group>(null)
  const outerSpin = useRef<Group>(null)
  const ring = useRef<Mesh>(null)
  const status = useRef<MeshStandardMaterial>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (dial.current) dial.current.rotation.z = t * 0.32
    if (outerSpin.current) outerSpin.current.rotation.z = -t * 0.12
    if (ring.current) {
      const mat = ring.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = 0.32 + Math.sin(t * 1.6) * 0.14
    }
    if (status.current) status.current.emissiveIntensity = 0.7 + Math.sin(t * 2.4) * 0.35
  })
  const bolts = Array.from({ length: 18 }, (_, i) => {
    const a = (i / 18) * Math.PI * 2
    return [Math.cos(a) * 1.18, Math.sin(a) * 1.18] as const
  })
  return (
    <group position={[0, 1.35, Z_BACK + 0.72]}>
      {/* Recessed vault alcove frame */}
      <mesh position={[0, 0.05, -0.35]}>
        <boxGeometry args={[4.4, 3.6, 0.5]} />
        <meshStandardMaterial color="#0c0814" metalness={0.45} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.05, -0.08]}>
        <boxGeometry args={[3.9, 3.2, 0.18]} />
        <meshStandardMaterial color="#16101f" metalness={0.55} roughness={0.4} />
      </mesh>
      {/* Brass arch trim */}
      <mesh position={[0, 1.55, 0.05]}>
        <boxGeometry args={[3.95, 0.08, 0.12]} />
        <meshStandardMaterial color={BRASS} metalness={0.88} roughness={0.2} />
      </mesh>
      <mesh position={[0, -1.5, 0.05]}>
        <boxGeometry args={[3.95, 0.1, 0.14]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[side * 1.95, 0.05, 0.05]}>
          <boxGeometry args={[0.1, 3.15, 0.12]} />
          <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
        </mesh>
      ))}
      {/* Inner chamber glow */}
      <mesh position={[0, 0.05, -0.55]}>
        <circleGeometry args={[1.15, 48]} />
        <meshBasicMaterial color="#3a1860" toneMapped={false} />
      </mesh>
      <pointLight position={[0, 0.2, -0.2]} intensity={0.85} color="#ffd080" distance={6} />
      <pointLight position={[0, 0.1, 0.5]} intensity={0.45} color="#7ef9ff" distance={5} />

      <group scale={1.05}>
        <mesh position={[0, 0, -0.08]}>
          <cylinderGeometry args={[1.55, 1.55, 0.22, 56]} />
          <meshStandardMaterial color="#080510" metalness={0.65} roughness={0.3} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[1.38, 1.38, 0.24, 56]} />
          <meshStandardMaterial color="#2a2438" metalness={0.8} roughness={0.22} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, 0.08]}>
          <cylinderGeometry args={[1.12, 1.12, 0.2, 56]} />
          <meshStandardMaterial color="#121018" metalness={0.75} roughness={0.26} />
        </mesh>
        {/* Spoke plate */}
        {Array.from({ length: 10 }).map((_, i) => {
          const a = (i / 10) * Math.PI
          return (
            <mesh key={i} position={[0, 0, 0.16]} rotation={[0, 0, a]}>
              <boxGeometry args={[2.15, 0.06, 0.045]} />
              <meshStandardMaterial color={BRASS} metalness={0.9} roughness={0.18} />
            </mesh>
          )
        })}
        {bolts.map(([bx, by], i) => (
          <mesh key={i} position={[bx, by, 0.2]}>
            <cylinderGeometry args={[0.05, 0.05, 0.06, 8]} />
            <meshStandardMaterial color="#9a8a48" metalness={0.85} roughness={0.25} />
          </mesh>
        ))}
        {/* Slow outer gear ring */}
        <group ref={outerSpin} position={[0, 0, 0.12]}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[1.42, 0.035, 10, 64]} />
            <meshStandardMaterial color={BRASS} metalness={0.9} roughness={0.2} emissive={BRASS} emissiveIntensity={0.2} />
          </mesh>
          {Array.from({ length: 24 }).map((_, i) => {
            const a = (i / 24) * Math.PI * 2
            return (
              <mesh key={i} position={[Math.cos(a) * 1.42, Math.sin(a) * 1.42, 0]} rotation={[0, 0, a]}>
                <boxGeometry args={[0.08, 0.045, 0.04]} />
                <meshStandardMaterial color="#8a7a40" metalness={0.8} roughness={0.28} />
              </mesh>
            )
          })}
        </group>
        <group ref={dial} position={[0, 0, 0.26]}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.36, 0.055, 12, 32]} />
            <meshStandardMaterial color={BRASS} metalness={0.92} roughness={0.16} emissive={BRASS} emissiveIntensity={0.45} />
          </mesh>
          <mesh>
            <boxGeometry args={[0.58, 0.05, 0.05]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <boxGeometry args={[0.34, 0.04, 0.04]} />
            <meshBasicMaterial color="#39ff14" toneMapped={false} />
          </mesh>
          <mesh position={[0, 0, 0.04]}>
            <sphereGeometry args={[0.08, 14, 14]} />
            <meshStandardMaterial color="#1a1420" metalness={0.7} roughness={0.3} emissive="#2de2e6" emissiveIntensity={0.5} />
          </mesh>
        </group>
        <mesh ref={ring} position={[0, 0, 0.1]}>
          <ringGeometry args={[1.22, 1.4, 56]} />
          <meshBasicMaterial color="#2de2e6" transparent opacity={0.3} depthWrite={false} toneMapped={false} />
        </mesh>
      </group>
      {/* SECURE status plaque */}
      <mesh position={[0, -1.85, 0.12]}>
        <boxGeometry args={[1.4, 0.28, 0.06]} />
        <meshStandardMaterial color={INK} metalness={0.5} roughness={0.35} />
      </mesh>
      <mesh position={[0, -1.85, 0.16]}>
        <boxGeometry args={[1.2, 0.14, 0.02]} />
        <meshStandardMaterial ref={status} color="#39ff14" emissive="#39ff14" emissiveIntensity={0.8} toneMapped={false} />
      </mesh>
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
  // Canvas plaque — stays on the seal (no Html billboard stuck to the player).
  const plaque = useMemo(() => {
    const c = document.createElement('canvas')
    c.width = 512
    c.height = 160
    const ctx = c.getContext('2d')!
    ctx.clearRect(0, 0, 512, 160)
    ctx.fillStyle = '#f9c80e'
    ctx.font = 'bold 42px Orbitron, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('APEX-CITY TRUST', 256, 58)
    ctx.fillStyle = '#9aa3c7'
    ctx.font = '28px Share Tech Mono, monospace'
    ctx.fillText(`${workers} TELLERS ON DUTY`, 256, 112)
    const tex = new CanvasTexture(c)
    tex.needsUpdate = true
    return tex
  }, [workers])
  useEffect(() => () => plaque.dispose(), [plaque])
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
    <group position={[0, 0.02, 3.55]} scale={0.68}>
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
      <mesh position={[0, 0.78, 0]}>
        <planeGeometry args={[2.2, 0.7]} />
        <meshBasicMaterial map={plaque} transparent toneMapped={false} depthWrite={false} />
      </mesh>
    </group>
  )
}

function LockboxWall({ bots }: { bots: BotRow[] }) {
  const leds = useRef<(Mesh | null)[]>([])
  const cells = useMemo(() => {
    const out = []
    for (let row = 0; row < 5; row++) {
      for (let col = 0; col < 3; col++) {
        const i = row * 3 + col
        const bot = bots[i % Math.max(bots.length, 1)]
        out.push({
          x: col * 0.38 - 0.38,
          y: row * 0.34 + 1.0,
          lit: Boolean(bot && bot.present !== false),
          color: beamColorFor(bot?.id, i),
          phase: i * 0.73,
        })
      }
    }
    return out
  }, [bots])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    leds.current.forEach((m, i) => {
      if (!m) return
      const c = cells[i]
      if (!c?.lit) return
      const blink = Math.sin(t * 2.1 + c.phase) > 0.82
      const mat = m.material as { color?: { set: (v: string) => void } }
      mat.color?.set(blink ? '#ffffff' : c.color)
    })
  })
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
          <mesh
            ref={(el) => {
              leds.current[i] = el
            }}
            position={[-0.08, 0.06, 0.05]}
          >
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
    <group position={[side * 4.2, 2.7, Z_BACK + 0.55]}>
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
      {/* Vault approach floor seal */}
      <mesh position={[0, 0.032, zBack + 2.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.05, 1.35, 48]} />
        <meshBasicMaterial color="#f9c80e" transparent opacity={0.28} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.033, zBack + 2.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.55, 0.7, 40]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.32} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.034, zBack + 2.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.35, 32]} />
        <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.25} />
      </mesh>

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
            <group key={`panel-${z}`} position={[side * (halfW - 0.12), 2.5, z]}>
              <mesh>
                <boxGeometry args={[0.05, 1.4, 1.6]} />
                <meshStandardMaterial color="#221838" roughness={0.65} metalness={0.2} />
              </mesh>
              <mesh position={[side * -0.03, 0, 0]}>
                <boxGeometry args={[0.02, 1.5, 1.7]} />
                <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.28} />
              </mesh>
              <mesh position={[side * -0.04, 0.45, 0]}>
                <boxGeometry args={[0.015, 0.04, 1.2]} />
                <meshBasicMaterial color={CYAN} toneMapped={false} />
              </mesh>
            </group>
          ))}
          {/* ATM / kiosk along side walls near portal */}
          <group position={[side * (halfW - 0.85), 0, zFront - 4.2]}>
            <mesh position={[0, 0.95, 0]} castShadow>
              <boxGeometry args={[0.55, 1.7, 0.4]} />
              <meshStandardMaterial color="#16101c" metalness={0.55} roughness={0.38} />
            </mesh>
            <mesh position={[side * -0.22, 1.25, 0]} rotation={[0, side * -0.05, 0]}>
              <boxGeometry args={[0.04, 0.45, 0.32]} />
              <meshStandardMaterial color={INK} metalness={0.5} roughness={0.3} />
            </mesh>
            <mesh position={[side * -0.25, 1.25, 0]}>
              <planeGeometry args={[0.38, 0.28]} />
              <meshBasicMaterial color={CYAN} toneMapped={false} />
            </mesh>
            <mesh position={[side * -0.22, 0.7, 0]}>
              <boxGeometry args={[0.03, 0.12, 0.22]} />
              <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
            </mesh>
            <mesh position={[0, 1.85, 0]}>
              <boxGeometry args={[0.5, 0.04, 0.36]} />
              <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
            </mesh>
            <pointLight position={[side * -0.4, 1.2, 0]} intensity={0.35} color="#7ef9ff" distance={3} />
          </group>
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

      {/* Ceiling slab — solid enclosure from every angle */}
      <mesh position={[0, ceilY + 0.1, midZ]}>
        <boxGeometry args={[width + wallT * 2 + 0.4, 0.28, depth + wallT + 0.4]} />
        <meshStandardMaterial color="#2a1a48" roughness={0.88} />
      </mesh>
      <mesh position={[0, ceilY - 0.01, midZ]}>
        <boxGeometry args={[width - 0.15, 0.08, depth - 0.15]} />
        <meshBasicMaterial color="#4a3278" toneMapped={false} />
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
          <mesh position={[0, 0.96, -0.15]}>
            <boxGeometry args={[0.9, 0.02, 0.04]} />
            <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
          </mesh>
        </group>
      ))}

      {/* Safe-deposit box wall flanking the vault door */}
      {([-1, 1] as const).map((side) => (
        <group key={`boxes-${side}`} position={[side * 3.35, 1.55, zBack + 0.35]}>
          <mesh>
            <boxGeometry args={[1.8, 2.4, 0.28]} />
            <meshStandardMaterial color="#16101c" metalness={0.55} roughness={0.4} />
          </mesh>
          {Array.from({ length: 4 }).map((_, row) =>
            Array.from({ length: 3 }).map((_, col) => (
              <mesh
                key={`${row}-${col}`}
                position={[(col - 1) * 0.5, 0.85 - row * 0.52, 0.16]}
              >
                <boxGeometry args={[0.42, 0.4, 0.04]} />
                <meshStandardMaterial color="#2a2438" metalness={0.65} roughness={0.32} />
              </mesh>
            )),
          )}
          {Array.from({ length: 4 }).map((_, row) =>
            Array.from({ length: 3 }).map((_, col) => (
              <mesh
                key={`knob-${row}-${col}`}
                position={[(col - 1) * 0.5 + 0.12, 0.85 - row * 0.52, 0.2]}
              >
                <cylinderGeometry args={[0.025, 0.025, 0.03, 8]} />
                <meshStandardMaterial color={BRASS} metalness={0.9} roughness={0.2} />
              </mesh>
            )),
          )}
          <mesh position={[0, 1.28, 0.16]}>
            <boxGeometry args={[1.7, 0.04, 0.05]} />
            <meshStandardMaterial color={BRASS} metalness={0.85} roughness={0.22} />
          </mesh>
        </group>
      ))}

      <WallClock position={[0, ceilY - 1.15, zBack + 0.2]} />
      <SecurityCam side={-1} x={-(halfW - 0.55)} y={ceilY - 0.55} z={midZ} />
      <SecurityCam side={1} x={halfW - 0.55} y={ceilY - 0.55} z={midZ} />
      <ServingSign side={-1} x={-1.35} z={midZ * 0.35} />
      <ServingSign side={1} x={1.35} z={midZ * 0.35 + 1.8} />
      <CeilingFan x={0} y={ceilY - 0.22} z={midZ * 0.15} />
      <CeilingFan x={0} y={ceilY - 0.22} z={-4.2} />

      {/* Planter boxes near the portal — soft leaf sway */}
      {([-1, 1] as const).map((side) => (
        <Planter key={`plant-${side}`} x={side * (portalW / 2 + 1.1)} z={zFront - 1.1} />
      ))}
    </group>
  )
}

function WallClock({ position }: { position: [number, number, number] }) {
  const hour = useRef<Group>(null)
  const minute = useRef<Group>(null)
  const second = useRef<Group>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    // Slow decorative clock — readable motion without needing real time.
    if (hour.current) hour.current.rotation.z = -t * 0.04
    if (minute.current) minute.current.rotation.z = -t * 0.22
    if (second.current) second.current.rotation.z = -t * 1.15
  })
  return (
    <group position={position}>
      <mesh>
        <cylinderGeometry args={[0.38, 0.38, 0.06, 28]} />
        <meshStandardMaterial color="#1a1424" metalness={0.5} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, 0.04]} rotation={[Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.32, 28]} />
        <meshBasicMaterial color="#0a0614" toneMapped={false} />
      </mesh>
      {Array.from({ length: 12 }, (_, i) => {
        const a = (i / 12) * Math.PI * 2
        return (
          <mesh key={i} position={[Math.sin(a) * 0.26, Math.cos(a) * 0.26, 0.05]}>
            <boxGeometry args={[0.018, 0.04, 0.01]} />
            <meshBasicMaterial color="#7ec8d8" toneMapped={false} />
          </mesh>
        )
      })}
      <group ref={hour} position={[0, 0, 0.055]}>
        <mesh position={[0, 0.09, 0]}>
          <boxGeometry args={[0.028, 0.18, 0.012]} />
          <meshBasicMaterial color="#f9c80e" toneMapped={false} />
        </mesh>
      </group>
      <group ref={minute} position={[0, 0, 0.06]}>
        <mesh position={[0, 0.12, 0]}>
          <boxGeometry args={[0.018, 0.24, 0.01]} />
          <meshBasicMaterial color="#2de2e6" toneMapped={false} />
        </mesh>
      </group>
      <group ref={second} position={[0, 0, 0.065]}>
        <mesh position={[0, 0.13, 0]}>
          <boxGeometry args={[0.01, 0.26, 0.008]} />
          <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
        </mesh>
      </group>
    </group>
  )
}

function SecurityCam({ side, x, y, z }: { side: -1 | 1; x: number; y: number; z: number }) {
  const head = useRef<Group>(null)
  const led = useRef<Mesh>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (head.current) {
      head.current.rotation.y = side * (0.35 + Math.sin(t * 0.35 + side) * 0.55)
      head.current.rotation.x = 0.35 + Math.sin(t * 0.55) * 0.08
    }
    if (led.current) {
      const mat = led.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = 0.55 + (Math.sin(t * 4.5 + side) > 0.7 ? 0.45 : 0)
    }
  })
  return (
    <group position={[x, y, z]}>
      <mesh>
        <boxGeometry args={[0.18, 0.1, 0.22]} />
        <meshStandardMaterial color="#1a1424" metalness={0.6} roughness={0.35} />
      </mesh>
      <group ref={head} position={[0, -0.04, 0.02]}>
        <mesh position={[0, -0.04, 0.06]} rotation={[0.4, 0, 0]}>
          <sphereGeometry args={[0.07, 12, 12]} />
          <meshStandardMaterial color="#0a1020" metalness={0.7} roughness={0.25} />
        </mesh>
        <mesh ref={led} position={[0, -0.06, 0.12]}>
          <sphereGeometry args={[0.025, 8, 8]} />
          <meshBasicMaterial color="#ff2a6d" transparent opacity={0.9} toneMapped={false} />
        </mesh>
      </group>
    </group>
  )
}

function ServingSign({ side, x, z }: { side: -1 | 1; x: number; z: number }) {
  const glow = useRef<Mesh>(null)
  const [ticket, setTicket] = useState(() => 100 + side * 12)
  useEffect(() => {
    const id = window.setInterval(() => {
      setTicket((n) => n + 1 + (Math.random() > 0.7 ? 1 : 0))
    }, 5200 + side * 900)
    return () => window.clearInterval(id)
  }, [side])
  useFrame(({ clock }) => {
    if (!glow.current) return
    const mat = glow.current.material as { emissiveIntensity?: number }
    if (mat.emissiveIntensity != null) {
      mat.emissiveIntensity = 0.25 + Math.sin(clock.getElapsedTime() * 2.8 + side) * 0.12
    }
  })
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 1.05, 0]}>
        <boxGeometry args={[0.06, 2.0, 0.06]} />
        <meshStandardMaterial color="#2a2438" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh ref={glow} position={[0, 2.05, 0.04]}>
        <boxGeometry args={[0.62, 0.36, 0.04]} />
        <meshStandardMaterial color={INK} emissive="#2de2e6" emissiveIntensity={0.28} />
      </mesh>
      <Html position={[0, 2.05, 0.08]} center distanceFactor={10} style={{ pointerEvents: 'none' }}>
        <div
          style={{
            fontFamily: 'Share Tech Mono, monospace',
            fontSize: '11px',
            color: '#39ff14',
            letterSpacing: '0.1em',
            textAlign: 'center',
            lineHeight: 1.25,
            textShadow: '0 0 8px rgba(57,255,20,0.45)',
            whiteSpace: 'nowrap',
          }}
        >
          NOW SERVING
          <div style={{ fontSize: '15px', color: '#f9c80e', marginTop: 2 }}>{String(ticket % 1000).padStart(3, '0')}</div>
        </div>
      </Html>
    </group>
  )
}

function CeilingFan({ x, y, z }: { x: number; y: number; z: number }) {
  const blades = useRef<Group>(null)
  useFrame((_, dt) => {
    if (blades.current) blades.current.rotation.y += dt * 2.1
  })
  return (
    <group position={[x, y, z]}>
      <mesh>
        <cylinderGeometry args={[0.08, 0.08, 0.14, 10]} />
        <meshStandardMaterial color="#2a2438" metalness={0.5} roughness={0.4} />
      </mesh>
      <mesh position={[0, -0.1, 0]}>
        <sphereGeometry args={[0.07, 10, 10]} />
        <meshBasicMaterial color="#7ef9ff" transparent opacity={0.55} toneMapped={false} />
      </mesh>
      <group ref={blades} position={[0, -0.08, 0]}>
        {[0, 1, 2, 3].map((i) => (
          <mesh key={i} rotation={[0, (i * Math.PI) / 2, 0]} position={[0.42, 0, 0]}>
            <boxGeometry args={[0.84, 0.025, 0.14]} />
            <meshStandardMaterial
              color="#3a2860"
              emissive="#2de2e6"
              emissiveIntensity={0.22}
              roughness={0.45}
              metalness={0.3}
            />
          </mesh>
        ))}
      </group>
    </group>
  )
}

function Planter({ x, z }: { x: number; z: number }) {
  const leaf = useRef<Group>(null)
  useFrame(({ clock }) => {
    if (!leaf.current) return
    const t = clock.getElapsedTime()
    leaf.current.rotation.z = Math.sin(t * 1.1 + x) * 0.06
    leaf.current.rotation.x = Math.cos(t * 0.9) * 0.04
  })
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.28, 0]}>
        <boxGeometry args={[0.7, 0.55, 0.45]} />
        <meshStandardMaterial color="#1a1428" roughness={0.7} />
      </mesh>
      <group ref={leaf}>
        <mesh position={[0, 0.58, 0]}>
          <sphereGeometry args={[0.28, 12, 10]} />
          <meshStandardMaterial color="#1a4a2a" roughness={0.85} />
        </mesh>
        <mesh position={[0.1, 0.72, 0.05]}>
          <sphereGeometry args={[0.16, 10, 8]} />
          <meshStandardMaterial color="#2a6a38" roughness={0.8} />
        </mesh>
      </group>
    </group>
  )
}

/** Sparse drifting motes — kept tiny so they don't read as floor clutter. */
function DataMotes() {
  const ref = useRef<Group>(null)
  const motes = useMemo(
    () =>
      Array.from({ length: 14 }, (_, i) => ({
        x: ((i * 47) % 100) / 100 * 8 - 4,
        z: ((i * 31) % 100) / 100 * 12 - 6,
        phase: i * 0.73,
        speed: 0.18 + (i % 4) * 0.05,
        drift: 0.15 + (i % 3) * 0.05,
        color: BEAM_COLORS[i % BEAM_COLORS.length],
        size: 0.03 + (i % 3) * 0.012,
      })),
    [],
  )
  useFrame(({ clock }) => {
    if (!ref.current) return
    const t = clock.getElapsedTime()
    ref.current.children.forEach((child, i) => {
      const m = motes[i]
      child.position.x = m.x + Math.sin(t * m.drift + m.phase) * 0.55
      child.position.y = 1.1 + ((t * m.speed + m.phase) % 3.2)
      child.position.z = m.z + Math.cos(t * m.drift * 0.8 + m.phase) * 0.4
      child.rotation.y = t * 0.5 + m.phase
    })
  })
  return (
    <group ref={ref}>
      {motes.map((m, i) => (
        <mesh key={i} position={[m.x, 1.8, m.z]}>
          <boxGeometry args={[m.size, m.size, m.size]} />
          <meshBasicMaterial color={m.color} transparent opacity={0.38} toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

/** Vault guard — short patrol along the back apron. */
function Warden() {
  const root = useRef<Group>(null)
  const label = useRef<Group>(null)
  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime()
    if (!root.current) return
    const x = 1.85 + Math.sin(t * 0.22) * 1.15
    const z = Z_BACK + 1.85 + Math.cos(t * 0.22) * 0.15
    root.current.position.x = MathUtils.damp(root.current.position.x, x, 2.2, dt)
    root.current.position.z = MathUtils.damp(root.current.position.z, z, 2.2, dt)
    // Face along the patrol arc, slightly toward the aisle.
    root.current.rotation.y = MathUtils.damp(
      root.current.rotation.y,
      Math.PI * 0.92 + Math.sin(t * 0.22) * 0.7,
      2.5,
      dt,
    )
    if (label.current) label.current.rotation.y = -root.current.rotation.y + Math.PI
  })
  return (
    <group ref={root} position={[1.85, 0.05, Z_BACK + 1.85]} rotation={[0, Math.PI * 0.92, 0]} scale={0.88}>
      <CityBotFigure context="bank" pose="waiting" seated={false} unitMark="00" seed={21} />
      <group ref={label}>
        <mesh position={[0, 2.15, 0.05]}>
          <boxGeometry args={[0.9, 0.14, 0.04]} />
          <meshStandardMaterial color={INK} emissive="#ff2a6d" emissiveIntensity={0.45} />
        </mesh>
        <mesh position={[0, 2.15, 0.08]}>
          <planeGeometry args={[0.82, 0.1]} />
          <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
        </mesh>
      </group>
    </group>
  )
}

/** Visual-only lobby patrons pacing the center aisle. */
function LobbyPatrons() {
  const paths = useMemo(
    () => [
      // Keep clear of player spawn (~z 5) so patrons don't read as the walker.
      { xAmp: 0.45, z0: 2.8, z1: -3.4, speed: 0.18, phase: 0.2, seed: 4, side: -0.65 },
      { xAmp: 0.35, z0: 1.6, z1: -6.2, speed: 0.14, phase: 2.4, seed: 9, side: 0.75 },
      { xAmp: 0.3, z0: 0.4, z1: -2.2, speed: 0.22, phase: 4.1, seed: 14, side: -0.2 },
    ],
    [],
  )
  const roots = useRef<(Group | null)[]>([])
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    paths.forEach((p, i) => {
      const g = roots.current[i]
      if (!g) return
      const u = (Math.sin(t * p.speed + p.phase) + 1) / 2
      const z = p.z0 + (p.z1 - p.z0) * u
      const x = p.side + Math.sin(t * p.speed * 1.4 + p.phase) * p.xAmp
      const prevZ = g.position.z
      g.position.x = x
      g.position.z = z
      g.position.y = 0.05 + Math.abs(Math.sin(t * 8 + p.phase)) * 0.02
      const goingBack = z < prevZ - 0.001
      const goingFwd = z > prevZ + 0.001
      if (goingBack) g.rotation.y = Math.PI
      else if (goingFwd) g.rotation.y = 0
    })
  })
  return (
    <group>
      {paths.map((p, i) => (
        <group
          key={i}
          ref={(el) => {
            roots.current[i] = el
          }}
          position={[p.side, 0.05, p.z0]}
          scale={0.82}
        >
          <CityBotFigure context="bank" pose="waiting" seated={false} seed={p.seed} />
        </group>
      ))}
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
  const rope = useRef<Group>(null)
  useFrame(({ clock }) => {
    if (!rope.current) return
    const sag = Math.sin(clock.getElapsedTime() * 1.4 + x * 3 + midZ) * 0.012
    rope.current.position.y = sag
    rope.current.rotation.z = sag * 0.8
  })
  return (
    <group ref={rope}>
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
  const [nearIndex, setNearIndex] = useState<number | null>(null)
  const [awayIndex, setAwayIndex] = useState<number | null>(null)
  const [recalling, setRecalling] = useState(false)
  const recallTimer = useRef<number | null>(null)
  const aisleLight = useRef<PointLight>(null)

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

  /** Desk cabinets + vault door as floor obstacles for the walker. */
  const obstacles = useMemo<FloorObstacle[]>(() => {
    const desks: FloorObstacle[] = tellers.map((_, i) => {
      const pose = slotPose(i)
      // Local AABB → world: local X along bank, local Z toward aisle/wall.
      const along = DESK_COLLIDE.halfW
      const towardAisle = DESK_COLLIDE.aisle
      const towardWall = DESK_COLLIDE.wall
      const cAisleX = pose.x + Math.sin(pose.rotY) * towardAisle
      const cAisleZ = pose.z + Math.cos(pose.rotY) * towardAisle
      const cWallX = pose.x - Math.sin(pose.rotY) * towardWall
      const cWallZ = pose.z - Math.cos(pose.rotY) * towardWall
      const sideX = Math.cos(pose.rotY) * along
      const sideZ = -Math.sin(pose.rotY) * along
      const xs = [cAisleX + sideX, cAisleX - sideX, cWallX + sideX, cWallX - sideX]
      const zs = [cAisleZ + sideZ, cAisleZ - sideZ, cWallZ + sideZ, cWallZ - sideZ]
      return {
        minX: Math.min(...xs),
        maxX: Math.max(...xs),
        minZ: Math.min(...zs),
        maxZ: Math.max(...zs),
      }
    })
    desks.push({ minX: -1.5, maxX: 1.5, minZ: Z_BACK + 0.4, maxZ: Z_BACK + 2.0 })
    return desks
  }, [tellers])

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

  useFrame(({ clock }) => {
    if (!aisleLight.current) return
    const t = clock.getElapsedTime()
    aisleLight.current.intensity = 1.05 + Math.sin(t * 1.15) * 0.12
  })

  return (
    <>
      <color attach="background" args={['#1a1030']} />
      <fog attach="fog" args={['#2a1a48', 28, 70]} />
      <PerspectiveCamera makeDefault fov={58} near={0.05} far={120} position={HOME_POS} />

      <PlayerBot
        active
        hallHalfW={HALL_W / 2}
        zBack={Z_BACK}
        zFront={Z_FRONT}
        obstacles={obstacles}
        tellerMouths={tellerMouths}
        onInteract={(id, index) => {
          setFocus(index)
          requestTeller(id, index)
        }}
        onHintChange={onWalkHint}
        onNearChange={setNearIndex}
      />

      <ambientLight intensity={0.7} color="#d8ceff" />
      <directionalLight position={[2.8, 6.5, 2.2]} intensity={0.7} color="#ffe9c8" castShadow={false} />
      <pointLight ref={aisleLight} position={[0, 3.2, 0]} intensity={1.15} color="#fff0b0" distance={20} />
      <pointLight position={[0, 2.9, Z_BACK + 1.6]} intensity={0.65} color="#7ef9ff" distance={14} />
      <pointLight position={[-HALL_W / 2 + 1.2, 2.6, 0]} intensity={0.45} color="#b967ff" distance={9} />
      <pointLight position={[HALL_W / 2 - 1.2, 2.6, 0]} intensity={0.45} color="#b967ff" distance={9} />

      <BankEnclosure />
      {/* Service walls behind each teller bank — close the room behind the bots */}
      {([-1, 1] as const).map((side) => {
        const wallX = side * (AISLE_HALF + 2.15)
        const rowMidZ = TELLER_Z0 - ((SIDE_COUNT - 1) * TELLER_SPACING) / 2
        const rowLen = SIDE_COUNT * TELLER_SPACING + 2.8
        return (
          <group key={`svc-${side}`}>
            <mesh position={[wallX, HALL_HEIGHT / 2, rowMidZ]}>
              <boxGeometry args={[0.28, HALL_HEIGHT - 0.1, rowLen]} />
              <meshBasicMaterial color="#4a3278" toneMapped={false} />
            </mesh>
            <mesh position={[wallX - side * 0.14, 0.72, rowMidZ]}>
              <boxGeometry args={[0.1, 1.4, rowLen - 0.2]} />
              <meshBasicMaterial color="#2a3848" toneMapped={false} />
            </mesh>
            <mesh position={[wallX - side * 0.16, 1.45, rowMidZ]}>
              <boxGeometry args={[0.05, 0.06, rowLen - 0.3]} />
              <meshBasicMaterial color="#2de2e6" toneMapped={false} />
            </mesh>
            <mesh position={[wallX - side * 0.16, HALL_HEIGHT - 0.35, rowMidZ]}>
              <boxGeometry args={[0.05, 0.05, rowLen - 0.3]} />
              <meshBasicMaterial color="#f9c80e" toneMapped={false} />
            </mesh>
            {/* Window numbers strip */}
            {Array.from({ length: SIDE_COUNT }, (_, row) => {
              const z = TELLER_Z0 - row * TELLER_SPACING
              return (
                <mesh key={row} position={[wallX - side * 0.18, 2.6, z]}>
                  <boxGeometry args={[0.04, 0.35, 0.55]} />
                  <meshBasicMaterial color="#1a1030" toneMapped={false} />
                </mesh>
              )
            })}
          </group>
        )
      })}
      <FloorGlowPaths tellers={tellers} />

      <HeroVaultDoor />
      <ProfitBoard desk={desk} />
      <LockboxWall bots={bots} />
      <CountingCage />
      <SideScreen side={-1} desk={desk} bots={bots} onOpen={onOpenDeskOps} />
      <SideScreen side={1} desk={desk} bots={bots} onOpen={onOpenDeskOps} />
      <TrustSeal workers={workers} />
      <Warden />
      <LobbyPatrons />
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
              near={nearIndex === i}
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

      <NeonBloom strength={0.08} />
    </>
  )
}
