import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { PerspectiveCamera } from '@react-three/drei'
import { DoubleSide, type Group } from 'three'
import type { BotRow, Desk } from '../types'
import { beamColorFor } from '../data/format'
import { activeWingRooms, type WingRoom } from '../data/officeWingLayout'
import {
  DOOR_HALF,
  ROOM_HALF_D,
  ROOM_HALF_W,
  SUITE_CONTENT_SCALE,
  WING_HALL,
  type WingSpawnMode,
} from '../data/wingWalk'
import { NeonBloom } from './Effects'
import { OfficeInterior } from './OfficeScene'
import { WingWalker } from './WingWalker'

type Props = {
  bot: BotRow
  bots: BotRow[]
  desk?: Desk
  /** Tower we entered from — walker spawns behind this bot once. */
  spawnBotId: string
  /** Suite / hall / boss — FloorNavMenu teleports. */
  spawnMode?: WingSpawnMode
  /** Proximity room change (does not re-spawn the walker). */
  onSelect: (id: string) => void
  onOpenScreens?: () => void
  /** Live control hint — same vault teller UX strings. */
  onWalkHint?: (hint: string) => void
}

const WALL_H = WING_HALL.wallH
const DOOR_W = DOOR_HALF * 2

const FLOOR = '#2e2650'
const FLOOR_TILE = '#352c5c'
const WALL = '#2a2048'
const WALL_DEEP = '#1a1430'
const TRIM = '#7ec8d8'
const WOOD = '#3a2a1c'
const METAL = '#c5ccd8'

/** Build solid hall wall segments along ±Z, leaving gaps at suite doorways. */
function hallWallSegments(side: 'left' | 'right'): { x: number; w: number }[] {
  const zEdge = side === 'left' ? WING_HALL.zMin : WING_HALL.zMax
  const doors = activeWingRooms()
    .filter((r) => {
      if (r.side === 'end') return false
      const doorZ = r.position[2] + Math.cos(r.yaw) * ROOM_HALF_D
      return Math.abs(doorZ - zEdge) < 0.35
    })
    .map((r) => r.position[0])
    .sort((a, b) => a - b)

  const gap = DOOR_W + 0.05
  const xStart = WING_HALL.xMin
  const xEnd = WING_HALL.xMax
  const segs: { x: number; w: number }[] = []
  let cursor = xStart
  for (const dx of doors) {
    const gapLo = dx - gap / 2
    const gapHi = dx + gap / 2
    if (gapLo > cursor + 0.08) {
      segs.push({ x: (cursor + gapLo) / 2, w: gapLo - cursor })
    }
    cursor = Math.max(cursor, gapHi)
  }
  if (xEnd > cursor + 0.08) {
    segs.push({ x: (cursor + xEnd) / 2, w: xEnd - cursor })
  }
  return segs
}

/** One useFrame spins every registered fan — avoids N per-fan subscriptions. */
type FanSpin = { blades: Group; speed: number }
const FAN_SPINS: FanSpin[] = []

function FanSpinDriver() {
  useFrame((_, dt) => {
    const step = Math.min(0.05, dt)
    for (let i = 0; i < FAN_SPINS.length; i++) {
      const f = FAN_SPINS[i]
      f.blades.rotation.y += step * f.speed * 1.35
    }
  })
  return null
}

function CeilingFan({ position, speed = 1 }: { position: [number, number, number]; speed?: number }) {
  const blades = useRef<Group>(null)
  useEffect(() => {
    const g = blades.current
    if (!g) return
    const entry: FanSpin = { blades: g, speed }
    FAN_SPINS.push(entry)
    return () => {
      const i = FAN_SPINS.indexOf(entry)
      if (i >= 0) FAN_SPINS.splice(i, 1)
    }
  }, [speed])
  return (
    <group position={position}>
      <mesh position={[0, 0.08, 0]}>
        <cylinderGeometry args={[0.06, 0.08, 0.1, 10]} />
        <meshStandardMaterial color={METAL} metalness={0.7} roughness={0.28} />
      </mesh>
      <mesh position={[0, -0.12, 0]}>
        <cylinderGeometry args={[0.018, 0.018, 0.28, 6]} />
        <meshStandardMaterial color="#8a93a5" metalness={0.65} roughness={0.3} />
      </mesh>
      <group ref={blades} position={[0, -0.28, 0]}>
        <mesh>
          <cylinderGeometry args={[0.1, 0.12, 0.06, 12]} />
          <meshStandardMaterial color="#1c222e" metalness={0.45} roughness={0.4} />
        </mesh>
        {/* Emissive hub reads as warm fill without a real pointLight per fan. */}
        <mesh position={[0, -0.04, 0]}>
          <sphereGeometry args={[0.05, 8, 8]} />
          <meshStandardMaterial color="#ffe8c8" emissive="#ffe8c8" emissiveIntensity={0.55} />
        </mesh>
        {([0, 1, 2, 3] as const).map((i) => (
          <group key={i} rotation={[0, (i * Math.PI) / 2, 0]}>
            <mesh position={[0.42, 0, 0]} rotation={[0.12, 0, 0]}>
              <boxGeometry args={[0.72, 0.02, 0.14]} />
              <meshStandardMaterial color="#d8c4a0" roughness={0.55} metalness={0.15} />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  )
}

function WallSconce({
  position,
  rotationY = 0,
  color = '#ffe2a0',
}: {
  position: [number, number, number]
  rotationY?: number
  color?: string
}) {
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh position={[0, 0, 0.02]}>
        <boxGeometry args={[0.12, 0.28, 0.04]} />
        <meshStandardMaterial color="#141820" metalness={0.45} roughness={0.4} />
      </mesh>
      <mesh position={[0, -0.02, 0.1]} rotation={[0.35, 0, 0]}>
        <boxGeometry args={[0.18, 0.06, 0.14]} />
        <meshStandardMaterial color="#f4e2a8" emissive={color} emissiveIntensity={0.85} roughness={0.35} />
      </mesh>
      {/* Glow via emissive only — dozens of sconce pointLights were the FPS killer. */}
      <mesh position={[0, -0.12, 0.18]}>
        <sphereGeometry args={[0.04, 6, 6]} />
        <meshBasicMaterial color={color} transparent opacity={0.55} toneMapped={false} />
      </mesh>
    </group>
  )
}

function ExitSign({ position, rotationY = 0 }: { position: [number, number, number]; rotationY?: number }) {
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh>
        <boxGeometry args={[0.55, 0.22, 0.06]} />
        <meshStandardMaterial color="#0a120a" metalness={0.3} roughness={0.45} />
      </mesh>
      <mesh position={[0, 0, 0.035]}>
        <boxGeometry args={[0.46, 0.14, 0.02]} />
        <meshBasicMaterial color="#39ff14" toneMapped={false} />
      </mesh>
    </group>
  )
}

function PottedPlant({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <group position={position} scale={scale}>
      <mesh position={[0, 0.16, 0]}>
        <cylinderGeometry args={[0.16, 0.13, 0.32, 8]} />
        <meshStandardMaterial color="#2a3344" roughness={0.55} metalness={0.2} />
      </mesh>
      <mesh position={[0, 0.42, 0]}>
        <sphereGeometry args={[0.22, 8, 8]} />
        <meshStandardMaterial color="#1d6b45" roughness={0.7} />
      </mesh>
      <mesh position={[0.12, 0.55, 0.05]}>
        <sphereGeometry args={[0.14, 7, 7]} />
        <meshStandardMaterial color="#2a8f5a" roughness={0.65} />
      </mesh>
      <mesh position={[-0.1, 0.52, -0.08]}>
        <sphereGeometry args={[0.12, 7, 7]} />
        <meshStandardMaterial color="#248a52" roughness={0.68} />
      </mesh>
    </group>
  )
}

function HallBench({ position, rotationY = 0 }: { position: [number, number, number]; rotationY?: number }) {
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh position={[0, 0.42, 0]}>
        <boxGeometry args={[1.35, 0.08, 0.48]} />
        <meshStandardMaterial color={WOOD} roughness={0.55} metalness={0.1} />
      </mesh>
      {([-0.55, 0.55] as const).map((x) => (
        <mesh key={x} position={[x, 0.22, 0]}>
          <boxGeometry args={[0.08, 0.36, 0.42]} />
          <meshStandardMaterial color="#1a2130" roughness={0.5} metalness={0.25} />
        </mesh>
      ))}
      <mesh position={[0, 0.72, -0.18]}>
        <boxGeometry args={[1.3, 0.42, 0.06]} />
        <meshStandardMaterial color="#241838" roughness={0.6} />
      </mesh>
    </group>
  )
}

function FramedArt({
  position,
  rotationY = 0,
  color,
  wide = false,
}: {
  position: [number, number, number]
  rotationY?: number
  color: string
  wide?: boolean
}) {
  const w = wide ? 1.15 : 0.72
  const h = wide ? 0.55 : 0.85
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh>
        <boxGeometry args={[w + 0.08, h + 0.08, 0.04]} />
        <meshStandardMaterial color="#10141c" metalness={0.4} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0, 0.025]}>
        <planeGeometry args={[w, h]} />
        <meshStandardMaterial color="#0c1020" emissive={color} emissiveIntensity={0.28} roughness={0.55} />
      </mesh>
      <mesh position={[0, h * 0.18, 0.03]}>
        <boxGeometry args={[w * 0.55, 0.03, 0.01]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
    </group>
  )
}

function HallCosmetics() {
  const x0 = (WING_HALL.xMin + WING_HALL.xMax) / 2
  const len = WING_HALL.xMax - WING_HALL.xMin
  const width = WING_HALL.zMax - WING_HALL.zMin
  const leftSegs = hallWallSegments('left')
  const rightSegs = hallWallSegments('right')
  const rooms = activeWingRooms()
  const tileXs = useMemo(() => {
    const out: number[] = []
    for (let x = Math.ceil(WING_HALL.xMin) + 0.5; x < WING_HALL.xMax; x += 1.05) out.push(x)
    return out
  }, [])
  const fanXs = [5, 11, 17, 23, 29]
  const sconceXs = [3.2, 7.4, 11.6, 15.8, 20, 24.2, 28.4]

  return (
    <group>
      {/* Layered hall floor — base slab + tile checker + neon runner + edge cove */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[x0, 0, 0]} receiveShadow={false}>
        <planeGeometry args={[len + 0.4, width + 0.25]} />
        <meshStandardMaterial color={FLOOR} roughness={0.62} metalness={0.12} side={DoubleSide} />
      </mesh>
      {tileXs.map((x, i) =>
        ([-0.85, 0.85] as const).map((z) => (
          <mesh
            key={`tile-${x}-${z}`}
            position={[x, 0.011, z]}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <planeGeometry args={[0.92, 0.72]} />
            <meshStandardMaterial
              color={i % 2 === 0 ? FLOOR_TILE : '#2a2248'}
              roughness={0.58}
              metalness={0.14}
            />
          </mesh>
        )),
      )}
      {/* Carpet runner with stitched edge */}
      <mesh position={[x0, 0.018, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[len - 0.5, 0.72]} />
        <meshStandardMaterial color="#1a3050" emissive="#2de2e6" emissiveIntensity={0.42} roughness={0.48} />
      </mesh>
      {([-0.38, 0.38] as const).map((z) => (
        <mesh key={`run-edge-${z}`} position={[x0, 0.019, z]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[len - 0.55, 0.04]} />
          <meshBasicMaterial color="#7ef9ff" toneMapped={false} />
        </mesh>
      ))}
      {/* Purple lane dashes */}
      {[4, 8, 12, 16, 20, 24, 28].map((x) => (
        <mesh key={`dash-${x}`} position={[x, 0.022, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.5, 0.16]} />
          <meshBasicMaterial color="#b967ff" toneMapped={false} />
        </mesh>
      ))}
      {/* Cove light strips along baseboards */}
      {([-1, 1] as const).map((s) => (
        <group key={`cove-${s}`}>
          <mesh position={[x0, 0.09, s * (width / 2 - 0.05)]}>
            <boxGeometry args={[len, 0.18, 0.07]} />
            <meshStandardMaterial color={TRIM} metalness={0.4} roughness={0.35} />
          </mesh>
          <mesh position={[x0, 0.2, s * (width / 2 - 0.08)]}>
            <boxGeometry args={[len - 0.4, 0.03, 0.03]} />
            <meshStandardMaterial color="#dff6ff" emissive="#7ef9ff" emissiveIntensity={0.55} />
          </mesh>
        </group>
      ))}

      {/* Hall side walls with wainscot + crown */}
      {leftSegs.map((seg) => (
        <group key={`hl-${seg.x}`} position={[seg.x, 0, WING_HALL.zMin + 0.06]}>
          <mesh position={[0, WALL_H / 2, 0]}>
            <boxGeometry args={[Math.max(0.2, seg.w), WALL_H, 0.18]} />
            <meshStandardMaterial color={WALL} roughness={0.8} metalness={0.08} />
          </mesh>
          <mesh position={[0, 0.55, 0.1]}>
            <boxGeometry args={[Math.max(0.15, seg.w - 0.08), 1.05, 0.04]} />
            <meshStandardMaterial color="#1b2130" roughness={0.75} />
          </mesh>
          <mesh position={[0, WALL_H - 0.08, 0.1]}>
            <boxGeometry args={[Math.max(0.15, seg.w - 0.05), 0.1, 0.06]} />
            <meshStandardMaterial color="#3a2a68" metalness={0.25} roughness={0.45} />
          </mesh>
        </group>
      ))}
      {rightSegs.map((seg) => (
        <group key={`hr-${seg.x}`} position={[seg.x, 0, WING_HALL.zMax - 0.06]}>
          <mesh position={[0, WALL_H / 2, 0]}>
            <boxGeometry args={[Math.max(0.2, seg.w), WALL_H, 0.18]} />
            <meshStandardMaterial color={WALL} roughness={0.8} metalness={0.08} />
          </mesh>
          <mesh position={[0, 0.55, -0.1]}>
            <boxGeometry args={[Math.max(0.15, seg.w - 0.08), 1.05, 0.04]} />
            <meshStandardMaterial color="#1b2130" roughness={0.75} />
          </mesh>
          <mesh position={[0, WALL_H - 0.08, -0.1]}>
            <boxGeometry args={[Math.max(0.15, seg.w - 0.05), 0.1, 0.06]} />
            <meshStandardMaterial color="#3a2a68" metalness={0.25} roughness={0.45} />
          </mesh>
        </group>
      ))}

      {/* Wall sconces + framed board art along the corridor */}
      {sconceXs.map((x, i) => (
        <group key={`sc-${x}`}>
          <WallSconce position={[x, 2.05, WING_HALL.zMin + 0.2]} rotationY={0} />
          <WallSconce position={[x, 2.05, WING_HALL.zMax - 0.2]} rotationY={Math.PI} />
          {i % 2 === 0 && (
            <FramedArt
              position={[x + 0.85, 1.85, WING_HALL.zMin + 0.2]}
              color={i % 4 === 0 ? '#2de2e6' : '#b967ff'}
            />
          )}
          {i % 2 === 1 && (
            <FramedArt
              position={[x - 0.85, 1.75, WING_HALL.zMax - 0.2]}
              rotationY={Math.PI}
              color={i % 3 === 0 ? '#f9c80e' : '#ff2a6d'}
              wide
            />
          )}
        </group>
      ))}

      {/* Outer building skin — continuous hull */}
      {(() => {
        const pad = 0.35
        const minX = WING_HALL.xMin - pad
        const maxX = 35.2 + ROOM_HALF_W + pad
        const minZ = -ROOM_HALF_D - ROOM_HALF_W - pad
        const maxZ = ROOM_HALF_D + ROOM_HALF_W + pad
        const midX = (minX + maxX) / 2
        const midZ = (minZ + maxZ) / 2
        const spanX = maxX - minX
        const spanZ = maxZ - minZ
        const t = 0.28
        return (
          <group>
            <mesh position={[midX, WALL_H / 2, minZ - t / 2]}>
              <boxGeometry args={[spanX + t * 2, WALL_H + 0.2, t]} />
              <meshStandardMaterial color="#120a24" roughness={0.92} />
            </mesh>
            <mesh position={[midX, WALL_H / 2, maxZ + t / 2]}>
              <boxGeometry args={[spanX + t * 2, WALL_H + 0.2, t]} />
              <meshStandardMaterial color="#120a24" roughness={0.92} />
            </mesh>
            <mesh position={[minX - t / 2, WALL_H / 2, midZ]}>
              <boxGeometry args={[t, WALL_H + 0.2, spanZ]} />
              <meshStandardMaterial color="#120a24" roughness={0.92} />
            </mesh>
            <mesh position={[maxX + t / 2, WALL_H / 2, midZ]}>
              <boxGeometry args={[t, WALL_H + 0.2, spanZ]} />
              <meshStandardMaterial color="#120a24" roughness={0.92} />
            </mesh>
            <mesh position={[midX, WALL_H + 0.08, midZ]} rotation={[Math.PI / 2, 0, 0]}>
              <planeGeometry args={[spanX + t * 2, spanZ + t * 2]} />
              <meshStandardMaterial color="#0e081c" roughness={0.95} side={DoubleSide} />
            </mesh>
          </group>
        )
      })()}

      {/* Door thresholds */}
      {rooms
        .filter((r) => r.side !== 'end')
        .map((r) => {
          const hallZ = r.position[2] < 0 ? WING_HALL.zMin : WING_HALL.zMax
          const doorZ = r.position[2] + Math.cos(r.yaw) * (ROOM_HALF_D - 0.05)
          return (
            <group key={`th-${r.id}`}>
              <mesh
                position={[r.position[0], 0.016, (doorZ + hallZ) / 2]}
                rotation={[-Math.PI / 2, 0, 0]}
              >
                <planeGeometry args={[DOOR_W + 0.55, Math.abs(doorZ - hallZ) + 0.55]} />
                <meshStandardMaterial color="#3a2a68" roughness={0.5} metalness={0.16} side={DoubleSide} />
              </mesh>
              {/* Metal door sill */}
              <mesh position={[r.position[0], 0.03, hallZ]}>
                <boxGeometry args={[DOOR_W + 0.35, 0.04, 0.12]} />
                <meshStandardMaterial color={METAL} metalness={0.7} roughness={0.28} />
              </mesh>
            </group>
          )
        })}
      <mesh position={[WING_HALL.xMax + 0.35, 0.016, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.1, DOOR_W + 0.5]} />
        <meshStandardMaterial color="#3a2a68" roughness={0.5} metalness={0.16} side={DoubleSide} />
      </mesh>

      {/* Ceiling tiles + troffers + spinning fans */}
      <mesh position={[x0, WALL_H, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[len + 0.4, width + 0.25]} />
        <meshStandardMaterial color="#161028" roughness={0.9} side={DoubleSide} />
      </mesh>
      {tileXs.filter((_, i) => i % 2 === 0).map((x) => (
        <mesh key={`ctile-${x}`} position={[x, WALL_H - 0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.95, width - 0.35]} />
          <meshStandardMaterial color="#1e1634" roughness={0.85} side={DoubleSide} />
        </mesh>
      ))}
      {[3, 7, 11, 15, 19, 23, 27].map((x) => (
        <group key={`troffer-${x}`}>
          <mesh position={[x, WALL_H - 0.05, 0]}>
            <boxGeometry args={[1.65, 0.06, 0.42]} />
            <meshBasicMaterial color="#e8f7ff" toneMapped={false} />
          </mesh>
          <mesh position={[x, WALL_H - 0.02, 0]}>
            <boxGeometry args={[1.75, 0.02, 0.5]} />
            <meshStandardMaterial color="#8aa0b8" metalness={0.55} roughness={0.3} />
          </mesh>
        </group>
      ))}
      {/* Sparse real fills — visual glow stays on emissive troffers/sconces. */}
      {[6, 14, 22, 29].map((x) => (
        <pointLight key={`fill-${x}`} position={[x, WALL_H - 0.55, 0]} intensity={0.55} color="#dff6ff" distance={11} />
      ))}
      {fanXs.map((x, i) => (
        <CeilingFan key={`fan-${x}`} position={[x, WALL_H - 0.12, 0]} speed={0.85 + (i % 3) * 0.12} />
      ))}

      {/* Entry lobby — arch, directory, plants, benches */}
      <group position={[WING_HALL.xMin + 0.2, 0, 0]}>
        <mesh position={[0, WALL_H / 2, 0]}>
          <boxGeometry args={[0.22, WALL_H, width + 0.45]} />
          <meshStandardMaterial color="#1a2130" metalness={0.4} roughness={0.4} />
        </mesh>
        <mesh position={[0.2, 2.55, 0]}>
          <boxGeometry args={[0.08, 0.28, 1.6]} />
          <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={0.7} />
        </mesh>
        <ExitSign position={[0.35, 2.9, 0]} />
        {/* Directory kiosk */}
        <mesh position={[1.15, 0.7, 0]}>
          <boxGeometry args={[0.42, 1.4, 0.65]} />
          <meshStandardMaterial color="#121820" metalness={0.4} roughness={0.4} />
        </mesh>
        <mesh position={[1.15, 1.45, 0.02]}>
          <boxGeometry args={[0.34, 0.55, 0.04]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
        <mesh position={[1.15, 0.95, 0.02]}>
          <boxGeometry args={[0.3, 0.18, 0.03]} />
          <meshStandardMaterial color="#0a1020" emissive="#2de2e6" emissiveIntensity={0.35} />
        </mesh>
        <PottedPlant position={[1.9, 0, -0.95]} scale={0.9} />
        <PottedPlant position={[1.9, 0, 0.95]} scale={0.9} />
        <HallBench position={[2.6, 0, -0.85]} />
        <HallBench position={[2.6, 0, 0.85]} rotationY={Math.PI} />
      </group>

      {/* Mid-hall lounge islands */}
      {[8.2, 16.4].map((x, i) => (
        <group key={`lounge-${x}`} position={[x, 0, 0]}>
          <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.95, 24]} />
            <meshStandardMaterial color="#221848" emissive="#b967ff" emissiveIntensity={0.12} roughness={0.8} />
          </mesh>
          <mesh position={[0, 0.32, 0]}>
            <cylinderGeometry args={[0.55, 0.6, 0.55, 16]} />
            <meshStandardMaterial color="#1a1030" roughness={0.65} />
          </mesh>
          <mesh position={[0, 0.62, 0]}>
            <cylinderGeometry args={[0.58, 0.58, 0.05, 16]} />
            <meshStandardMaterial color="#2a1a48" metalness={0.2} roughness={0.45} />
          </mesh>
          <PottedPlant position={[-0.75, 0, 0]} scale={0.75} />
          <mesh position={[0.7, 0.55, 0]}>
            <boxGeometry args={[0.08, 1.05, 0.08]} />
            <meshStandardMaterial color={METAL} metalness={0.7} roughness={0.25} />
          </mesh>
          <mesh position={[0.7, 1.12, 0]}>
            <sphereGeometry args={[0.1, 12, 12]} />
            <meshStandardMaterial color="#f4e2a8" emissive="#f9c80e" emissiveIntensity={0.65} />
          </mesh>
          <mesh position={[0, 1.35, 0]}>
            <sphereGeometry args={[0.08, 8, 8]} />
            <meshBasicMaterial color={i === 0 ? '#b967ff' : '#2de2e6'} transparent opacity={0.7} toneMapped={false} />
          </mesh>
          <FramedArt position={[0, 2.15, WING_HALL.zMin + 0.22]} color="#2de2e6" wide />
        </group>
      ))}

      {/* Water cooler + trash + fire cabinet near boss end */}
      <group position={[26.2, 0, 0.95]}>
        <mesh position={[0, 0.55, 0]}>
          <cylinderGeometry args={[0.18, 0.2, 1.1, 12]} />
          <meshStandardMaterial color={METAL} metalness={0.55} roughness={0.3} />
        </mesh>
        <mesh position={[0, 1.25, 0]}>
          <sphereGeometry args={[0.22, 12, 12]} />
          <meshStandardMaterial color="#7ef9ff" transparent opacity={0.55} roughness={0.2} />
        </mesh>
        <mesh position={[0.28, 0.85, 0.05]}>
          <boxGeometry args={[0.08, 0.12, 0.08]} />
          <meshStandardMaterial color="#1a2130" metalness={0.4} roughness={0.4} />
        </mesh>
      </group>
      <mesh position={[25.4, 0.28, -0.95]}>
        <cylinderGeometry args={[0.16, 0.14, 0.55, 12]} />
        <meshStandardMaterial color="#141820" roughness={0.55} metalness={0.25} />
      </mesh>
      <group position={[27.4, 1.1, -1.25]}>
        <mesh>
          <boxGeometry args={[0.45, 0.7, 0.18]} />
          <meshStandardMaterial color="#5a1018" metalness={0.35} roughness={0.45} />
        </mesh>
        <mesh position={[0, 0, 0.1]}>
          <boxGeometry args={[0.2, 0.35, 0.04]} />
          <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
        </mesh>
      </group>
      <ExitSign position={[WING_HALL.xMax - 0.8, 2.95, 0]} />
      <PottedPlant position={[29.2, 0, -1.05]} />
      <PottedPlant position={[29.2, 0, 1.05]} />
      <HallBench position={[22.5, 0, -1.05]} />
      <HallBench position={[22.5, 0, 1.05]} rotationY={Math.PI} />
    </group>
  )
}

function SuiteShell({ room, color, live }: { room: WingRoom; color: string; live: boolean }) {
  const doorGap = DOOR_W
  const wallSeg = (ROOM_HALF_W * 2 - doorGap) / 2
  const isBoss = Boolean(room.boss)
  return (
    <group position={room.position} rotation={[0, room.yaw, 0]}>
      {/* Carpet floor + border tile ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <planeGeometry args={[ROOM_HALF_W * 2, ROOM_HALF_D * 2]} />
        <meshStandardMaterial
          color={isBoss ? '#2a1a40' : '#221a3c'}
          roughness={0.66}
          metalness={0.1}
          side={DoubleSide}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.014, 0]}>
        <planeGeometry args={[ROOM_HALF_W * 2 - 0.7, ROOM_HALF_D * 2 - 0.7]} />
        <meshStandardMaterial color={isBoss ? '#1e1234' : '#1a1430'} roughness={0.72} metalness={0.08} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, -0.35]}>
        <circleGeometry args={[isBoss ? 1.7 : 1.35, 28]} />
        <meshStandardMaterial color="#221848" emissive={color} emissiveIntensity={0.2} roughness={0.82} />
      </mesh>

      {/* Walls with wainscot + crown */}
      {([-ROOM_HALF_W, ROOM_HALF_W] as const).map((x) => (
        <group key={`sx-${x}`}>
          <mesh position={[x, WALL_H / 2, 0]}>
            <boxGeometry args={[0.14, WALL_H, ROOM_HALF_D * 2]} />
            <meshStandardMaterial color={WALL} roughness={0.86} />
          </mesh>
          <mesh position={[x + (x > 0 ? -0.08 : 0.08), 0.52, 0]}>
            <boxGeometry args={[0.04, 1.0, ROOM_HALF_D * 2 - 0.2]} />
            <meshStandardMaterial color="#1b2130" roughness={0.75} />
          </mesh>
          <mesh position={[x + (x > 0 ? -0.08 : 0.08), WALL_H - 0.1, 0]}>
            <boxGeometry args={[0.05, 0.1, ROOM_HALF_D * 2 - 0.15]} />
            <meshStandardMaterial color="#3a2a68" roughness={0.45} metalness={0.2} />
          </mesh>
        </group>
      ))}
      <mesh position={[0, WALL_H / 2, -ROOM_HALF_D]}>
        <boxGeometry args={[ROOM_HALF_W * 2, WALL_H, 0.14]} />
        <meshStandardMaterial color={WALL} roughness={0.86} />
      </mesh>
      {/* Window mullions + panes */}
      <mesh position={[0, 1.75, -ROOM_HALF_D + 0.06]}>
        <planeGeometry args={[ROOM_HALF_W * 1.25, 1.95]} />
        <meshStandardMaterial color="#0a1828" roughness={0.32} metalness={0.45} />
      </mesh>
      {([-1.4, 0, 1.4] as const).map((x) => (
        <mesh key={`mull-${x}`} position={[x, 1.75, -ROOM_HALF_D + 0.09]}>
          <boxGeometry args={[0.05, 1.9, 0.04]} />
          <meshStandardMaterial color="#8b95a8" metalness={0.65} roughness={0.28} />
        </mesh>
      ))}
      <mesh position={[0, 1.75, -ROOM_HALF_D + 0.11]}>
        <planeGeometry args={[ROOM_HALF_W * 1.15, 1.7]} />
        <meshBasicMaterial color="#7ef9ff" transparent opacity={0.1} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.72, -ROOM_HALF_D + 0.12]}>
        <boxGeometry args={[ROOM_HALF_W * 1.3, 0.08, 0.16]} />
        <meshStandardMaterial color="#0e1218" metalness={0.4} roughness={0.4} />
      </mesh>

      {/* Suite ceiling + fan + troffer */}
      <mesh position={[0, WALL_H, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[ROOM_HALF_W * 2 + 0.1, ROOM_HALF_D * 2 + 0.1]} />
        <meshStandardMaterial color="#161028" roughness={0.9} side={DoubleSide} />
      </mesh>
      <mesh position={[0, WALL_H - 0.05, -0.3]}>
        <boxGeometry args={[2.2, 0.05, 0.4]} />
        <meshBasicMaterial color="#e8f7ff" toneMapped={false} />
      </mesh>
      <CeilingFan position={[0, WALL_H - 0.1, 0.6]} speed={isBoss ? 0.7 : 1} />

      {/* Hall wall with open doorway */}
      <mesh position={[-(doorGap / 2 + wallSeg / 2), WALL_H / 2, ROOM_HALF_D]}>
        <boxGeometry args={[wallSeg, WALL_H, 0.14]} />
        <meshStandardMaterial color={WALL_DEEP} roughness={0.85} />
      </mesh>
      <mesh position={[doorGap / 2 + wallSeg / 2, WALL_H / 2, ROOM_HALF_D]}>
        <boxGeometry args={[wallSeg, WALL_H, 0.14]} />
        <meshStandardMaterial color={WALL_DEEP} roughness={0.85} />
      </mesh>
      {/* Door jambs + header with glow */}
      {([-doorGap / 2, doorGap / 2] as const).map((x) => (
        <mesh key={`df-${x}`} position={[x, 1.2, ROOM_HALF_D]}>
          <boxGeometry args={[0.08, 2.4, 0.1]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
        </mesh>
      ))}
      <mesh position={[0, 2.42, ROOM_HALF_D]}>
        <boxGeometry args={[doorGap + 0.12, 0.1, 0.1]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
      </mesh>
      {/* Name plate */}
      <mesh position={[doorGap / 2 + 0.62, 1.9, ROOM_HALF_D + 0.05]}>
        <boxGeometry args={[0.85, 0.32, 0.05]} />
        <meshStandardMaterial color="#10141c" metalness={0.4} roughness={0.35} />
      </mesh>
      <mesh position={[doorGap / 2 + 0.62, 1.9, ROOM_HALF_D + 0.09]}>
        <boxGeometry args={[0.7, 0.14, 0.02]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      {isBoss && (
        <mesh position={[0, 2.75, ROOM_HALF_D + 0.07]}>
          <boxGeometry args={[1.1, 0.18, 0.05]} />
          <meshBasicMaterial color="#f9c80e" toneMapped={false} />
        </mesh>
      )}

      {/* Non-live suite desk set */}
      {!live && (
        <group position={[0, 0, -0.35]}>
          <mesh position={[0, 0.76, 0]}>
            <boxGeometry args={[2.8, 0.09, 1.15]} />
            <meshStandardMaterial color="#12151c" metalness={0.35} roughness={0.45} />
          </mesh>
          <mesh position={[0, 0.72, 0.52]}>
            <boxGeometry args={[2.8, 0.025, 0.04]} />
            <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.4} />
          </mesh>
          {([-0.85, 0, 0.85] as const).map((x, i) => (
            <mesh key={x} position={[x, 1.2, -0.42]} rotation={[0, x * 0.12, 0]}>
              <boxGeometry args={[0.7, 0.48, 0.05]} />
              <meshStandardMaterial
                color="#0c1018"
                emissive={color}
                emissiveIntensity={0.18 + i * 0.04}
                metalness={0.3}
                roughness={0.4}
              />
            </mesh>
          ))}
          <mesh position={[0, 0.52, 0.75]}>
            <boxGeometry args={[0.58, 0.72, 0.58]} />
            <meshStandardMaterial color="#1c2433" roughness={0.55} />
          </mesh>
          <mesh position={[0.95, 0.95, 0.1]}>
            <coneGeometry args={[0.08, 0.1, 12, 1, true]} />
            <meshStandardMaterial color="#f4e2a8" emissive="#f9c80e" emissiveIntensity={0.75} side={DoubleSide} />
          </mesh>
        </group>
      )}

      {/* Decor: plants, bookshelf, wall art, sconce, bin */}
      <PottedPlant position={[-ROOM_HALF_W + 0.55, 0, -ROOM_HALF_D + 0.75]} scale={0.95} />
      <PottedPlant position={[ROOM_HALF_W - 0.55, 0, ROOM_HALF_D - 1.1]} scale={0.7} />
      <mesh position={[ROOM_HALF_W - 0.42, 1.15, -0.15]}>
        <boxGeometry args={[0.38, 1.85, 1.15]} />
        <meshStandardMaterial color="#161b26" roughness={0.5} metalness={0.2} />
      </mesh>
      {[0.4, 0.85, 1.3, 1.75].map((y) => (
        <mesh key={`shelf-${y}`} position={[ROOM_HALF_W - 0.42, y, -0.15]}>
          <boxGeometry args={[0.36, 0.03, 1.1]} />
          <meshStandardMaterial color={WOOD} roughness={0.55} />
        </mesh>
      ))}
      <FramedArt position={[-ROOM_HALF_W + 0.1, 1.9, 0.4]} rotationY={Math.PI / 2} color={color} />
      <FramedArt
        position={[ROOM_HALF_W - 0.1, 1.85, 1.2]}
        rotationY={-Math.PI / 2}
        color={isBoss ? '#f9c80e' : '#2de2e6'}
        wide
      />
      <WallSconce position={[-ROOM_HALF_W + 0.12, 2.15, -1.2]} rotationY={Math.PI / 2} color={color} />
      <WallSconce position={[ROOM_HALF_W - 0.12, 2.15, -1.2]} rotationY={-Math.PI / 2} color={color} />
      <mesh position={[-ROOM_HALF_W + 0.7, 0.18, ROOM_HALF_D - 0.7]}>
        <cylinderGeometry args={[0.12, 0.1, 0.35, 10]} />
        <meshStandardMaterial color="#12151c" metalness={0.3} roughness={0.5} />
      </mesh>
      {/* Only the live suite pays for real point lights — idle rooms stay emissive-lit. */}
      {live && (
        <>
          <pointLight position={[0, 2.55, 0]} intensity={0.55} color={color} distance={8} />
          <pointLight position={[0, 2.2, -ROOM_HALF_D + 0.8]} intensity={0.28} color="#9ecbff" distance={5.5} />
        </>
      )}
    </group>
  )
}

/**
 * Continuous walkable trading wing — hallway + open suites + boss.
 * Spawn behind the focused tower bot; WASD walks the whole floor (no room-click teleport).
 */
export function OfficeHallScene({
  bot,
  bots,
  desk,
  spawnBotId,
  spawnMode = 'suite',
  onSelect,
  onOpenScreens,
  onWalkHint,
}: Props) {
  const rooms = useMemo(() => activeWingRooms(), [])

  return (
    <>
      <color attach="background" args={['#12082a']} />
      <fog attach="fog" args={['#14082e', 38, 92]} />
      <PerspectiveCamera makeDefault fov={58} near={0.06} far={140} position={[10, 1.9, 0]} />
      <ambientLight intensity={0.82} color="#d4c8ff" />
      <directionalLight position={[12, 16, 6]} intensity={0.48} color="#f2e8ff" />
      <hemisphereLight args={['#c8dcff', '#1a1030', 0.5]} />
      <pointLight position={[10, 2.5, 0]} intensity={0.4} color="#7ef9ff" distance={18} />
      <pointLight position={[22, 2.3, 0]} intensity={0.28} color="#b967ff" distance={14} />

      <FanSpinDriver />
      <HallCosmetics />

      {rooms.map((room, i) => {
        const color = beamColorFor(room.botId, i)
        const live = room.botId === bot.id
        return <SuiteShell key={room.id} room={room} color={color} live={live} />
      })}

      {/* Live trading desk — embedded so SuiteShell doorway connects to the hall. */}
      {rooms.map((room) => {
        if (room.botId !== bot.id) return null
        const row = bots.find((b) => b.id === room.botId) || bot
        return (
          <group
            key={`live-${room.id}`}
            position={room.position}
            rotation={[0, room.yaw, 0]}
            scale={SUITE_CONTENT_SCALE}
          >
            <OfficeInterior
              bot={row}
              bots={bots}
              desk={desk}
              onOpenScreens={onOpenScreens}
              embedded
            />
          </group>
        )
      })}

      <WingWalker
        active
        focusBotId={spawnBotId}
        spawnMode={spawnMode}
        onEnterRoom={(id) => {
          if (id !== bot.id) onSelect(id)
        }}
        onOpenScreens={onOpenScreens}
        onHintChange={onWalkHint}
      />

      <NeonBloom strength={0.18} lite />
    </>
  )
}
