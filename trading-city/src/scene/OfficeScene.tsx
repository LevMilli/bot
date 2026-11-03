import { useEffect, useMemo, useRef, useState } from 'react'
import { OrbitControls, PerspectiveCamera } from '@react-three/drei'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { DoubleSide, type Group, type Texture } from 'three'
import type { BotRow, Desk } from '../types'
import { useFrame } from '@react-three/fiber'
import {
  centerMonitorTexture,
  leftMonitorTexture,
  rightMonitorTexture,
} from '../hud/monitorTextures'
import { botPose } from '../data/botPose'
import { NeonBloom } from './Effects'
import { BotFigure } from './BotFigure'
import { StreetCity } from './WindowCity'
import { KEY_TOP, MOUSE_TOP, mouseHand } from './deskReach'
import { WallStockChart } from './WallCharts'
import { OfficeFloorPlan } from './OfficeFloorPlan'
import { clampOfficeWalk, officeZoneForZ, type OfficeWalkZone } from '../data/officeWalk'

type FloorFocus = 'suite' | 'hall' | 'boss'

type Props = {
  bot: BotRow
  bots?: BotRow[]
  desk?: Desk
  onOpenScreens?: () => void
  onEnterHall?: () => void
  onEnterBoss?: () => void
  onSelectBot?: (id: string) => void
  floorFocus?: FloorFocus
}

const FRAME = '#3a2a68'
const WALL = '#241848'
const TRIM = '#7ec8d8'

function MonitorFrame({
  position,
  rotation,
  size,
  edge,
  map,
  onOpen,
}: {
  position: [number, number, number]
  rotation: [number, number, number]
  size: [number, number]
  edge: string
  map: Texture
  onOpen?: () => void
}) {
  const [w, h] = size
  return (
    <group
      position={position}
      rotation={rotation}
      onClick={(e) => {
        e.stopPropagation()
        onOpen?.()
      }}
      onPointerOver={() => {
        document.body.style.cursor = 'pointer'
      }}
      onPointerOut={() => {
        document.body.style.cursor = 'default'
      }}
    >
      <mesh>
        <boxGeometry args={[w, h, 0.05]} />
        <meshStandardMaterial color="#0c1018" metalness={0.35} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, 0.028]}>
        <planeGeometry args={[w * 0.9, h * 0.84]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      {/* Thin glass sheen so screens read as embedded panels, not floating HUD. */}
      <mesh position={[0, 0, 0.034]} raycast={() => null}>
        <planeGeometry args={[w * 0.9, h * 0.84]} />
        <meshStandardMaterial
          color="#9fdfff"
          transparent
          opacity={0.08}
          metalness={0.85}
          roughness={0.12}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>
      <mesh position={[0, h / 2 + 0.012, 0.02]}>
        <boxGeometry args={[w + 0.03, 0.022, 0.03]} />
        <meshBasicMaterial color={edge} toneMapped={false} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.012, 0.02]}>
        <boxGeometry args={[w + 0.03, 0.022, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[-w / 2 - 0.012, 0, 0.02]}>
        <boxGeometry args={[0.022, h + 0.02, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[w / 2 + 0.012, 0, 0.02]}>
        <boxGeometry args={[0.022, h + 0.02, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      {/* stand */}
      <mesh position={[0, -h / 2 - 0.16, 0.04]}>
        <boxGeometry args={[0.06, 0.26, 0.06]} />
        <meshStandardMaterial color="#1c222e" metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.28, 0.06]}>
        <boxGeometry args={[0.28, 0.02, 0.16]} />
        <meshStandardMaterial color="#1c222e" metalness={0.55} roughness={0.35} />
      </mesh>
    </group>
  )
}

function Ceiling() {
  const tiles: [number, number][] = []
  for (let x = -2; x <= 2; x++) {
    for (let z = -1; z <= 2; z++) {
      tiles.push([x * 1.55, z * 1.35 - 0.4])
    }
  }
  return (
    <group>
      <mesh position={[0, 3.38, 0.7]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[16, 8.2]} />
        <meshStandardMaterial color="#1a1230" roughness={0.92} side={DoubleSide} />
      </mesh>
      {tiles.map(([x, z]) => (
        <mesh key={`${x}-${z}`} position={[x, 3.36, z]} rotation={[Math.PI / 2, 0, 0]}>
          <planeGeometry args={[1.42, 1.18]} />
          <meshStandardMaterial color="#261848" roughness={0.85} metalness={0.04} side={DoubleSide} />
        </mesh>
      ))}
      {/* troffer lights across the bay */}
      {([-1.15, 1.15] as const).map((x) =>
        ([-1.1, 0.35, 1.8] as const).map((z) => (
          <mesh key={`${x}-${z}`} position={[x, 3.34, z]}>
            <boxGeometry args={[0.28, 0.04, 1.15]} />
            <meshBasicMaterial color="#e7f6ff" toneMapped={false} />
          </mesh>
        )),
      )}
      {/* HVAC vents + cable tray for whole-room reads */}
      {([-2.4, 2.4] as const).map((x) => (
        <group key={`vent-${x}`} position={[x, 3.32, -0.8]}>
          <mesh>
            <boxGeometry args={[0.9, 0.04, 0.55]} />
            <meshStandardMaterial color="#2a3344" metalness={0.5} roughness={0.4} />
          </mesh>
          {([-0.16, -0.05, 0.06, 0.17] as const).map((z) => (
            <mesh key={z} position={[0, -0.02, z]}>
              <boxGeometry args={[0.78, 0.01, 0.035]} />
              <meshStandardMaterial color="#0c1018" roughness={0.7} />
            </mesh>
          ))}
        </group>
      ))}
      <mesh position={[0, 3.3, 2.55]}>
        <boxGeometry args={[10.5, 0.06, 0.18]} />
        <meshStandardMaterial color="#141820" metalness={0.55} roughness={0.35} />
      </mesh>
      {([-3.5, -1.5, 0.5, 2.5] as const).map((x) => (
        <mesh key={`tray-${x}`} position={[x, 3.22, 2.55]}>
          <boxGeometry args={[0.08, 0.12, 0.08]} />
          <meshStandardMaterial color="#2de2e6" emissive="#2de2e6" emissiveIntensity={0.35} />
        </mesh>
      ))}
    </group>
  )
}

function SideWall({ x, rot }: { x: number; rot: number }) {
  return (
    <group position={[x, 1.69, 0.7]} rotation={[0, rot, 0]}>
      <mesh>
        <planeGeometry args={[8.2, 3.38]} />
        <meshStandardMaterial color={WALL} roughness={0.9} side={DoubleSide} />
      </mesh>
      <mesh position={[0, -0.85, 0.01]}>
        <planeGeometry args={[8.2, 1.35]} />
        <meshStandardMaterial color="#1b212e" roughness={0.82} side={DoubleSide} />
      </mesh>
      <mesh position={[0, -0.16, 0.02]}>
        <boxGeometry args={[8.2, 0.04, 0.02]} />
        <meshStandardMaterial color={TRIM} metalness={0.35} roughness={0.45} />
      </mesh>
      <mesh position={[0, -1.66, 0.02]}>
        <boxGeometry args={[8.2, 0.06, 0.03]} />
        <meshStandardMaterial color="#0d1118" metalness={0.4} roughness={0.4} />
      </mesh>
    </group>
  )
}

function Door() {
  return (
    <group position={[-7.85, 1.15, 1.35]} rotation={[0, Math.PI / 2, 0]}>
      <mesh position={[0, 0, 0.02]}>
        <boxGeometry args={[1.05, 2.25, 0.06]} />
        <meshStandardMaterial color="#0e121a" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0, 0.06]}>
        <boxGeometry args={[0.92, 2.12, 0.02]} />
        <meshStandardMaterial color="#171c28" roughness={0.6} />
      </mesh>
      <mesh position={[0.32, 0, 0.09]}>
        <boxGeometry args={[0.04, 0.16, 0.04]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
      </mesh>
    </group>
  )
}

function Credenza() {
  return (
    <group position={[3.15, 0.42, -1.15]}>
      <mesh>
        <boxGeometry args={[0.55, 0.78, 1.7]} />
        <meshStandardMaterial color="#161b26" metalness={0.25} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.08, 0.28]}>
        <boxGeometry args={[0.52, 0.02, 0.7]} />
        <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, -0.22, 0.28]}>
        <boxGeometry args={[0.52, 0.02, 0.7]} />
        <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.4} />
      </mesh>
      {/* Rack gear instead of a plant — keeps the office plant-free. */}
      <mesh position={[-0.12, 0.52, 0]}>
        <boxGeometry args={[0.28, 0.22, 0.36]} />
        <meshStandardMaterial color="#0c1018" metalness={0.55} roughness={0.35} />
      </mesh>
      {([-0.06, 0, 0.06] as const).map((y, i) => (
        <mesh key={y} position={[-0.12, 0.52 + y, 0.185]}>
          <boxGeometry args={[0.22, 0.018, 0.012]} />
          <meshBasicMaterial
            color={i === 1 ? '#39ff14' : '#2de2e6'}
            toneMapped={false}
          />
        </mesh>
      ))}
      <mesh position={[-0.22, 0.64, 0]}>
        <cylinderGeometry args={[0.02, 0.02, 0.08, 10]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.75} roughness={0.28} />
      </mesh>
      {([0.15, 0.28, 0.4] as const).map((z, i) => (
        <mesh key={z} position={[0.02, 0.46 + i * 0.035, z]}>
          <boxGeometry args={[0.42, 0.03, 0.28]} />
          <meshStandardMaterial color={i === 1 ? '#1a3a55' : '#121820'} roughness={0.6} />
        </mesh>
      ))}
    </group>
  )
}

function OfficeChair() {
  const spokes = [0, 1, 2, 3, 4]
  return (
    <group position={[0, 0, 0.86]}>
      <mesh position={[0, 0.31, 0]}>
        <cylinderGeometry args={[0.045, 0.05, 0.5, 12]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.85} roughness={0.22} />
      </mesh>
      {spokes.map((i) => {
        const a = (i / 5) * Math.PI * 2
        return (
          <group key={i} rotation={[0, a, 0]}>
            <mesh position={[0.18, 0.08, 0]}>
              <boxGeometry args={[0.32, 0.035, 0.05]} />
              <meshStandardMaterial color="#141820" metalness={0.5} roughness={0.4} />
            </mesh>
            <mesh position={[0.34, 0.05, 0]}>
              <sphereGeometry args={[0.045, 10, 10]} />
              <meshStandardMaterial color="#0c0e14" roughness={0.45} />
            </mesh>
          </group>
        )
      })}
      {/* Cushion under the hips and thighs. The front lip stops at the knees. */}
      <mesh position={[0, 0.6, 0.1]}>
        <boxGeometry args={[0.98, 0.08, 0.36]} />
        <meshStandardMaterial color="#12151c" roughness={0.7} />
      </mesh>
      {/* Tall black backrest — white cross + twin green bars from the office ref. */}
      <mesh position={[0, 1.18, 0.38]}>
        <boxGeometry args={[0.58, 0.92, 0.07]} />
        <meshStandardMaterial color="#0a0c12" roughness={0.55} metalness={0.25} />
      </mesh>
      <mesh position={[0, 1.18, 0.42]}>
        <boxGeometry args={[0.045, 0.62, 0.012]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.38, 0.42]}>
        <boxGeometry args={[0.28, 0.045, 0.012]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      {([-0.16, 0.16] as const).map((x) => (
        <mesh key={x} position={[x, 1.18, 0.42]}>
          <boxGeometry args={[0.03, 0.7, 0.01]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
      ))}
      {([-0.58, 0.58] as const).map((x) => (
        <group key={x}>
          <mesh position={[x, 0.78, 0.16]}>
            <boxGeometry args={[0.04, 0.28, 0.04]} />
            <meshStandardMaterial color="#1c222e" metalness={0.4} roughness={0.4} />
          </mesh>
          <mesh position={[x, 0.92, 0.16]}>
            <boxGeometry args={[0.06, 0.028, 0.26]} />
            <meshStandardMaterial color="#1c222e" metalness={0.4} roughness={0.4} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

function WindowWall() {
  return (
    <group position={[0, 0, -3.55]}>
      {/* opaque surround */}
      <mesh position={[0, 3.28, 0]}>
        <boxGeometry args={[16, 0.28, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      <mesh position={[0, 0.38, 0]}>
        <boxGeometry args={[16, 0.76, 0.16]} />
        <meshStandardMaterial color="#3a455c" roughness={0.8} />
      </mesh>
      <mesh position={[-5.7, 1.9, 0]}>
        <boxGeometry args={[4.6, 2.7, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      <mesh position={[5.7, 1.9, 0]}>
        <boxGeometry args={[4.6, 2.7, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>

      {/* curtain-wall frame */}
      <mesh position={[0, 0.78, 0.04]}>
        <boxGeometry args={[7.05, 0.08, 0.08]} />
        <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, 3.12, 0.04]}>
        <boxGeometry args={[7.05, 0.08, 0.08]} />
        <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
      </mesh>
      {([-3.48, 3.48] as const).map((x) => (
        <mesh key={x} position={[x, 1.95, 0.04]}>
          <boxGeometry args={[0.08, 2.42, 0.08]} />
          <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
        </mesh>
      ))}
      {([-1.15, 1.15] as const).map((x) => (
        <mesh key={`m-${x}`} position={[x, 1.95, 0.07]}>
          <boxGeometry args={[0.045, 2.28, 0.05]} />
          <meshStandardMaterial color="#8b95a8" metalness={0.7} roughness={0.28} />
        </mesh>
      ))}

      {/* Clear glass. The city meshes sit outside this opening. */}
      <mesh position={[0, 1.95, 0.02]} raycast={() => null}>
        <planeGeometry args={[6.82, 2.26]} />
        <meshBasicMaterial
          color="#b7fff8"
          transparent
          opacity={0.06}
          depthWrite={false}
          side={DoubleSide}
          toneMapped={false}
        />
      </mesh>
      {/* faint glass sheen in front of the mullions' plane */}
      <mesh position={[0, 1.95, 0.09]} raycast={() => null}>
        <planeGeometry args={[6.82, 2.26]} />
        <meshBasicMaterial color="#b7fff8" transparent opacity={0.05} depthWrite={false} side={DoubleSide} />
      </mesh>

      {/* exterior sill */}
      <mesh position={[0, 0.72, -0.18]}>
        <boxGeometry args={[7.2, 0.06, 0.28]} />
        <meshStandardMaterial color="#0e1218" metalness={0.4} roughness={0.45} />
      </mesh>
      {/* interior blind rails — depth when you orbit the window wall */}
      {([-2.4, -0.8, 0.8, 2.4] as const).map((x) => (
        <mesh key={`blind-${x}`} position={[x, 2.85, 0.12]}>
          <boxGeometry args={[0.04, 0.55, 0.04]} />
          <meshStandardMaterial color="#8b95a8" metalness={0.6} roughness={0.3} />
        </mesh>
      ))}
      <mesh position={[0, 3.05, 0.14]}>
        <boxGeometry args={[6.6, 0.04, 0.05]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.7} roughness={0.28} />
      </mesh>
    </group>
  )
}

function Desk() {
  return (
    <group>
      <mesh position={[0, 0.76, -0.15]}>
        <boxGeometry args={[3.7, 0.08, 1.45]} />
        <meshStandardMaterial color="#1a3a68" metalness={0.42} roughness={0.38} />
      </mesh>
      <mesh position={[0, 0.805, -0.15]}>
        <boxGeometry args={[3.62, 0.008, 1.36]} />
        <meshStandardMaterial
          color="#2450a0"
          emissive="#143878"
          emissiveIntensity={0.22}
          metalness={0.55}
          roughness={0.28}
        />
      </mesh>
      <mesh position={[0, 0.72, 0.52]}>
        <boxGeometry args={[3.7, 0.025, 0.04]} />
        <meshStandardMaterial color="#2de2e6" emissive="#2de2e6" emissiveIntensity={0.45} metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.42, -0.72]}>
        <boxGeometry args={[3.55, 0.58, 0.06]} />
        <meshStandardMaterial color="#10141c" roughness={0.75} />
      </mesh>
      {([-1.55, 1.55] as const).map((x) => (
        <mesh key={x} position={[x, 0.38, 0.15]}>
          <boxGeometry args={[0.08, 0.72, 1.15]} />
          <meshStandardMaterial color="#1a1f2a" metalness={0.3} roughness={0.5} />
        </mesh>
      ))}
      <mesh position={[0.15, 0.81, 0.15]}>
        <boxGeometry args={[0.55, 0.02, 0.2]} />
        <meshStandardMaterial color="#0c0e14" roughness={0.5} />
      </mesh>
      <mesh position={[-1.5, 0.82, 0.15]} rotation={[-Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.13, 0.13, 0.045, 24]} />
        <meshStandardMaterial color="#c01028" emissive="#ff2040" emissiveIntensity={0.7} roughness={0.35} />
      </mesh>
    </group>
  )
}

function OfficeFloor() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0.7]}>
        <planeGeometry args={[16, 8.3]} />
        <meshStandardMaterial color="#0a0418" roughness={0.68} metalness={0.18} side={DoubleSide} />
      </mesh>
      <gridHelper args={[9, 18, '#5ef6ff', '#3a1888']} position={[0, 0.014, 0.55]} />
      {/* Soft cyan wash under the desk so the synthwave grid reads from OTS. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.016, 0.35]} raycast={() => null}>
        <planeGeometry args={[4.2, 3.2]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.04} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  )
}

const HOME_POS: [number, number, number] = [0.15, 1.78, 3.35]
const HOME_TARGET: [number, number, number] = [0, 1.42, 0.05]
// Stand just inside the hall (glass is at z≈4.78) looking down the corridor.
const HALL_POS: [number, number, number] = [0.15, 2.35, 6.4]
const HALL_TARGET: [number, number, number] = [0, 1.45, 14]
const BOSS_POS: [number, number, number] = [0.3, 2.6, 18]
const BOSS_TARGET: [number, number, number] = [0, 1.5, 26]

/** Extra room dressing for whole-room look-around. Adds only — keeps the desk kit intact. */
function RoomDressing() {
  return (
    <group>
      {/* Left bookshelf — fills the wall when you orbit past the chart */}
      <group position={[-3.9, 0, 1.85]}>
        <mesh position={[0, 1.15, 0]}>
          <boxGeometry args={[0.42, 2.2, 1.35]} />
          <meshStandardMaterial color="#12151c" metalness={0.25} roughness={0.55} />
        </mesh>
        {([-0.75, -0.25, 0.25, 0.75] as const).map((z, row) => (
          <group key={z} position={[0.02, 0.45 + row * 0.42, z * 0.05]}>
            <mesh position={[0, 0, 0]}>
              <boxGeometry args={[0.36, 0.03, 1.2]} />
              <meshStandardMaterial color="#1c2433" roughness={0.5} />
            </mesh>
            {([-0.4, -0.15, 0.1, 0.35] as const).map((bz, i) => (
              <mesh key={bz} position={[0.08, 0.14, bz]}>
                <boxGeometry args={[0.18, 0.24, 0.12]} />
                <meshStandardMaterial
                  color={i % 2 ? '#1a3a55' : '#2a1848'}
                  emissive={i === 1 ? '#2de2e6' : '#000'}
                  emissiveIntensity={i === 1 ? 0.15 : 0}
                  roughness={0.65}
                />
              </mesh>
            ))}
          </group>
        ))}
      </group>

      {/* Filing cabinets by the door */}
      <group position={[-6.4, 0.5, 0.15]}>
        {([0, 0.55] as const).map((z) => (
          <group key={z} position={[0, 0, z]}>
            <mesh>
              <boxGeometry args={[0.55, 1.0, 0.48]} />
              <meshStandardMaterial color="#161b26" metalness={0.35} roughness={0.45} />
            </mesh>
            {([-0.22, 0.05, 0.32] as const).map((y) => (
              <mesh key={y} position={[0.28, y, 0]}>
                <boxGeometry args={[0.02, 0.04, 0.22]} />
                <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
              </mesh>
            ))}
          </group>
        ))}
      </group>

      {/* Blinky rack in the far right corner — plant-free tech prop */}
      <group position={[5.6, 0, 2.4]}>
        <mesh position={[0, 0.95, 0]}>
          <boxGeometry args={[0.7, 1.9, 0.55]} />
          <meshStandardMaterial color="#0a0c12" metalness={0.55} roughness={0.35} />
        </mesh>
        {Array.from({ length: 10 }, (_, i) => (
          <mesh key={i} position={[0.32, 0.25 + i * 0.16, 0]}>
            <boxGeometry args={[0.04, 0.06, 0.42]} />
            <meshBasicMaterial
              color={i % 3 === 0 ? '#39ff14' : i % 3 === 1 ? '#2de2e6' : '#f9c80e'}
              toneMapped={false}
            />
          </mesh>
        ))}
        <pointLight position={[0.2, 1.2, 0.4]} intensity={0.35} color="#2de2e6" distance={3.5} />
      </group>

      {/* Neighbor empty desk bay — foreshadows a walkable office floor */}
      <group position={[4.2, 0, -0.35]}>
        <mesh position={[0, 0.76, 0]}>
          <boxGeometry args={[2.2, 0.07, 1.1]} />
          <meshStandardMaterial color="#16345e" metalness={0.4} roughness={0.4} />
        </mesh>
        {([-0.9, 0.9] as const).map((x) => (
          <mesh key={x} position={[x, 0.38, 0.1]}>
            <boxGeometry args={[0.07, 0.68, 0.9]} />
            <meshStandardMaterial color="#1a1f2a" roughness={0.55} />
          </mesh>
        ))}
        <mesh position={[0, 1.15, -0.35]}>
          <boxGeometry args={[0.85, 0.5, 0.04]} />
          <meshStandardMaterial color="#0c1018" metalness={0.4} roughness={0.4} />
        </mesh>
        <mesh position={[0, 1.15, -0.32]}>
          <planeGeometry args={[0.72, 0.4]} />
          <meshBasicMaterial color="#061018" toneMapped={false} />
        </mesh>
        <mesh position={[0, 1.32, -0.31]}>
          <boxGeometry args={[0.78, 0.02, 0.02]} />
          <meshBasicMaterial color="#7a849f" toneMapped={false} />
        </mesh>
        <mesh position={[0, 0.015, 0.55]} rotation={[-Math.PI / 2, 0, 0]}>
          <circleGeometry args={[0.55, 20]} />
          <meshStandardMaterial color="#140e2a" roughness={0.9} />
        </mesh>
        {/* vacant chair silhouette */}
        <mesh position={[0, 0.55, 0.7]}>
          <boxGeometry args={[0.55, 0.08, 0.5]} />
          <meshStandardMaterial color="#12151c" roughness={0.7} />
        </mesh>
        <mesh position={[0, 0.95, 0.92]}>
          <boxGeometry args={[0.5, 0.7, 0.06]} />
          <meshStandardMaterial color="#0a0c12" roughness={0.55} />
        </mesh>
      </group>

      {/* Under-desk PC + cable run */}
      <group position={[-1.35, 0.28, 0.05]}>
        <mesh>
          <boxGeometry args={[0.28, 0.48, 0.42]} />
          <meshStandardMaterial color="#0c1018" metalness={0.5} roughness={0.4} />
        </mesh>
        <mesh position={[0.145, 0.1, 0]}>
          <boxGeometry args={[0.02, 0.08, 0.08]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
        <mesh position={[0.145, -0.05, 0.08]}>
          <boxGeometry args={[0.02, 0.04, 0.04]} />
          <meshBasicMaterial color="#2de2e6" toneMapped={false} />
        </mesh>
      </group>
      <mesh position={[-0.4, 0.03, 0.55]} rotation={[0, 0.4, 0]}>
        <boxGeometry args={[1.6, 0.02, 0.04]} />
        <meshStandardMaterial color="#1a2433" roughness={0.6} />
      </mesh>

      {/* Whiteboard / sticky wall by left chart */}
      <group position={[-3.4, 1.7, -1.55]} rotation={[0, 0.35, 0]}>
        <mesh>
          <boxGeometry args={[1.4, 0.95, 0.04]} />
          <meshStandardMaterial color="#d7e6ff" roughness={0.55} />
        </mesh>
        <mesh position={[0, 0, 0.025]}>
          <planeGeometry args={[1.28, 0.82]} />
          <meshBasicMaterial color="#eef4ff" toneMapped={false} />
        </mesh>
        {([-0.35, 0, 0.35] as const).map((x, i) => (
          <mesh key={x} position={[x, 0.2 - i * 0.05, 0.03]}>
            <boxGeometry args={[0.22, 0.18, 0.01]} />
            <meshStandardMaterial
              color={i === 0 ? '#39ff14' : i === 1 ? '#f9c80e' : '#ff2a6d'}
              emissive={i === 0 ? '#1a6a44' : '#000'}
              emissiveIntensity={0.2}
            />
          </mesh>
        ))}
      </group>

      {/* Corner floor LEDs so orbit reads room bounds */}
      {([
        [-6.5, 3.5],
        [6.5, 3.5],
        [-6.5, -2.2],
        [6.5, -2.2],
      ] as const).map(([x, z]) => (
        <mesh key={`${x}-${z}`} position={[x, 0.04, z]}>
          <boxGeometry args={[0.35, 0.03, 0.08]} />
          <meshBasicMaterial color="#b967ff" toneMapped={false} />
        </mesh>
      ))}

      {/* Door surround + exit glow (keeps the existing Door mesh visible) */}
      <mesh position={[-7.85, 2.45, 1.35]}>
        <boxGeometry args={[0.35, 0.12, 0.08]} />
        <meshBasicMaterial color="#39ff14" toneMapped={false} />
      </mesh>
      <mesh position={[-7.86, 2.35, 1.35]} rotation={[0, Math.PI / 2, 0]}>
        <boxGeometry args={[1.28, 0.08, 0.1]} />
        <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.45} />
      </mesh>
      {([-0.58, 0.58] as const).map((z) => (
        <mesh key={z} position={[-7.86, 1.15, 1.35 + z]} rotation={[0, Math.PI / 2, 0]}>
          <boxGeometry args={[0.1, 2.35, 0.1]} />
          <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.45} />
        </mesh>
      ))}
    </group>
  )
}

function DeskKit() {
  const mouse = useRef<Group>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!mouse.current) return
    const pose = mouseHand(t)
    mouse.current.position.x = pose.x
    mouse.current.position.z = pose.z
    mouse.current.rotation.y = pose.yaw
  })
  const keys: [number, number][] = []
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 12; col++) {
      keys.push([col, row])
    }
  }
  return (
    <group>
      {/* keyboard in reach of the left hand */}
      <group position={[-0.3, KEY_TOP - 0.022, 0.34]}>
        <mesh>
          <boxGeometry args={[0.52, 0.02, 0.18]} />
          <meshStandardMaterial color="#2c3548" metalness={0.35} roughness={0.45} />
        </mesh>
        {keys.map(([col, row]) => (
          <mesh key={`${col}-${row}`} position={[-0.22 + col * 0.04, 0.016, -0.06 + row * 0.038]}>
            <boxGeometry args={[0.03, 0.012, 0.028]} />
            <meshStandardMaterial
              color={row === 0 ? '#d7fff8' : '#c5d0e0'}
              emissive={row === 0 ? '#2de2e6' : '#1a2433'}
              emissiveIntensity={row === 0 ? 0.45 : 0.15}
              metalness={0.2}
              roughness={0.4}
            />
          </mesh>
        ))}
      </group>
      {/* mouse pad + mouse under the right hand */}
      <mesh position={[0.48, 0.802, 0.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.28, 0.22]} />
        <meshStandardMaterial color="#10141c" roughness={0.8} />
      </mesh>
      <group ref={mouse} position={[0.48, MOUSE_TOP - 0.02, 0.4]}>
        <mesh>
          <boxGeometry args={[0.07, 0.028, 0.11]} />
          <meshStandardMaterial color="#d8fff8" emissive="#7ef9ff" emissiveIntensity={0.25} metalness={0.4} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.016, -0.01]}>
          <boxGeometry args={[0.028, 0.008, 0.04]} />
          <meshStandardMaterial color="#39ff14" emissive="#39ff14" emissiveIntensity={0.6} />
        </mesh>
      </group>
      {/* Lamp between left + center monitors, base on near desk edge; shade aims into the gap. */}
      <group position={[-0.75, 0.8, 0.22]}>
        <mesh position={[0, 0.02, 0]}>
          <cylinderGeometry args={[0.07, 0.09, 0.03, 16]} />
          <meshStandardMaterial color="#1c222e" metalness={0.6} roughness={0.35} />
        </mesh>
        <mesh position={[0, 0.2, 0]}>
          <cylinderGeometry args={[0.014, 0.014, 0.32, 8]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh position={[0, 0.3, -0.14]} rotation={[-0.95, 0, 0]}>
          <cylinderGeometry args={[0.011, 0.011, 0.24, 8]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh position={[0, 0.26, -0.26]} rotation={[-1.15, 0, 0]}>
          <coneGeometry args={[0.08, 0.07, 16, 1, true]} />
          <meshStandardMaterial color="#f4e2a8" emissive="#f9c80e" emissiveIntensity={0.55} side={DoubleSide} />
        </mesh>
      </group>
      <pointLight position={[-0.75, 1.05, 0.05]} intensity={0.45} color="#ffe2a0" distance={2.2} />
      {/* Extra desk clutter — headphones, phone pad, sticky stack, pen cup */}
      <group position={[-0.95, 0.84, 0.28]}>
        <mesh rotation={[0.2, 0.4, 0]}>
          <torusGeometry args={[0.08, 0.015, 8, 20]} />
          <meshStandardMaterial color="#1c222e" metalness={0.5} roughness={0.4} />
        </mesh>
        <mesh position={[0.08, 0, 0]} rotation={[1.2, 0, 0.3]}>
          <boxGeometry args={[0.04, 0.06, 0.03]} />
          <meshStandardMaterial color="#2de2e6" emissive="#2de2e6" emissiveIntensity={0.25} />
        </mesh>
      </group>
      <mesh position={[1.15, 0.805, 0.35]} rotation={[-Math.PI / 2, 0, 0.2]}>
        <circleGeometry args={[0.09, 16]} />
        <meshStandardMaterial color="#10141c" roughness={0.7} />
      </mesh>
      <mesh position={[1.15, 0.82, 0.35]}>
        <boxGeometry args={[0.07, 0.012, 0.12]} />
        <meshStandardMaterial color="#1a2433" metalness={0.4} roughness={0.4} />
      </mesh>
      {([0, 1, 2] as const).map((i) => (
        <mesh key={i} position={[1.35, 0.812 + i * 0.008, 0.05]} rotation={[-0.05, 0.15 * i, 0]}>
          <boxGeometry args={[0.1, 0.006, 0.1]} />
          <meshStandardMaterial
            color={i === 0 ? '#39ff14' : i === 1 ? '#f9c80e' : '#ff2a6d'}
            roughness={0.7}
          />
        </mesh>
      ))}
      <group position={[-1.55, 0.84, 0.35]}>
        <mesh>
          <cylinderGeometry args={[0.045, 0.04, 0.08, 12]} />
          <meshStandardMaterial color="#1a2433" roughness={0.55} />
        </mesh>
        {([-0.015, 0.015] as const).map((x) => (
          <mesh key={x} position={[x, 0.08, 0]} rotation={[0.15, 0, x * 4]}>
            <cylinderGeometry args={[0.006, 0.006, 0.14, 6]} />
            <meshStandardMaterial color="#c5ccd8" metalness={0.6} roughness={0.35} />
          </mesh>
        ))}
      </group>
      {/* mug and notebook */}
      <group position={[0.92, 0.84, 0.22]}>
        <mesh>
          <cylinderGeometry args={[0.045, 0.04, 0.07, 16]} />
          <meshStandardMaterial color="#101820" roughness={0.4} metalness={0.3} />
        </mesh>
        <mesh position={[0, 0.02, 0]}>
          <cylinderGeometry args={[0.038, 0.038, 0.02, 16]} />
          <meshStandardMaterial color="#3a2418" roughness={0.5} />
        </mesh>
        <mesh position={[0.055, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.022, 0.006, 6, 12]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.7} roughness={0.3} />
        </mesh>
      </group>
      <mesh position={[-1.35, 0.812, -0.15]} rotation={[-0.04, -0.4, 0]}>
        <boxGeometry args={[0.2, 0.012, 0.26]} />
        <meshStandardMaterial color="#1a2744" roughness={0.7} />
      </mesh>
      <mesh position={[-1.35, 0.82, -0.15]} rotation={[-0.04, -0.4, 0]}>
        <boxGeometry args={[0.16, 0.004, 0.2]} />
        <meshBasicMaterial color="#d7e6ff" />
      </mesh>
      {/* bin and rug */}
      <mesh position={[1.85, 0.16, 0.95]}>
        <cylinderGeometry args={[0.12, 0.1, 0.32, 12]} />
        <meshStandardMaterial color="#12151c" metalness={0.35} roughness={0.5} />
      </mesh>
      <mesh position={[0.05, 0.015, 0.9]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.85, 24]} />
        <meshStandardMaterial color="#1a1038" roughness={0.9} />
      </mesh>
      {/* coat rack by the door */}
      <group position={[-6.35, 0, 2.15]}>
        <mesh position={[0, 0.7, 0]}>
          <cylinderGeometry args={[0.03, 0.04, 1.4, 8]} />
          <meshStandardMaterial color="#2a3344" metalness={0.5} roughness={0.4} />
        </mesh>
        <mesh position={[0, 1.42, 0]}>
          <sphereGeometry args={[0.05, 10, 10]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.7} roughness={0.3} />
        </mesh>
        <mesh position={[0.08, 1.05, 0.02]} rotation={[0.15, 0, 0.2]}>
          <boxGeometry args={[0.28, 0.42, 0.06]} />
          <meshStandardMaterial color="#123044" roughness={0.6} />
        </mesh>
      </group>
    </group>
  )
}

export function OfficeScene({
  bot,
  bots,
  desk,
  onOpenScreens,
  onEnterHall,
  onEnterBoss,
  onSelectBot,
  floorFocus = 'suite',
}: Props) {
  const controls = useRef<OrbitControlsImpl>(null)
  const pose = useMemo(() => botPose(bot), [bot])
  const [doorOpen, setDoorOpen] = useState(false)

  const maps = useMemo(() => {
    const left = leftMonitorTexture(bot)
    const center = centerMonitorTexture(bot, desk)
    const right = rightMonitorTexture(bot)
    return { left, center, right }
  }, [bot, desk])

  useEffect(() => {
    return () => {
      maps.left.dispose()
      maps.center.dispose()
      maps.right.dispose()
    }
  }, [maps])

  useEffect(() => {
    const orbit = controls.current
    const cam = orbit?.object
    if (!orbit || !cam) return
    if (floorFocus === 'boss') {
      cam.position.set(...BOSS_POS)
      orbit.target.set(...BOSS_TARGET)
      setDoorOpen(true)
    } else if (floorFocus === 'hall') {
      cam.position.set(...HALL_POS)
      orbit.target.set(...HALL_TARGET)
      setDoorOpen(true)
    } else {
      cam.position.set(...HOME_POS)
      orbit.target.set(...HOME_TARGET)
    }
    orbit.update()
  }, [bot.id, floorFocus])

  // Same walk physics as vault teller: W/S · ↑/↓ move along look vector; clamp to floor zones.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const key = e.key.toLowerCase()
      if (!(key === 'arrowup' || key === 'w' || key === 'arrowdown' || key === 's')) return
      e.preventDefault()
      const orbit = controls.current
      if (!orbit) return
      const cam = orbit.object
      const lx = orbit.target.x - cam.position.x
      const lz = orbit.target.z - cam.position.z
      const len = Math.hypot(lx, lz) || 1
      const dir = key === 'arrowup' || key === 'w' ? 1 : -1
      const step = 0.42 * dir
      const nx = lx / len
      const nz = lz / len
      const zoneHint: OfficeWalkZone =
        floorFocus === 'boss' ? 'boss' : floorFocus === 'hall' ? 'hall' : officeZoneForZ(orbit.target.z)
      const nextTarget = clampOfficeWalk(
        orbit.target.x + nx * step,
        orbit.target.z + nz * step,
        zoneHint,
      )
      const ox = orbit.target.x
      const oz = orbit.target.z
      orbit.target.x = nextTarget.x
      orbit.target.z = nextTarget.z
      cam.position.x += nextTarget.x - ox
      cam.position.z += nextTarget.z - oz
      const camZone = officeZoneForZ(cam.position.z)
      const camClamp = clampOfficeWalk(cam.position.x, cam.position.z, camZone)
      cam.position.x = camClamp.x
      cam.position.z = camClamp.z
      if (nextTarget.z > 4.5) setDoorOpen(true)
      orbit.update()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [floorFocus])

  return (
    <>
      <color attach="background" args={['#0a0418']} />
      <fog attach="fog" args={['#100628', 22, 90]} />
      <PerspectiveCamera makeDefault fov={48} near={0.08} far={140} position={HOME_POS} />
      <OrbitControls
        ref={controls}
        makeDefault
        target={HOME_TARGET}
        enableDamping
        dampingFactor={0.08}
        enablePan
        screenSpacePanning
        minDistance={0.95}
        maxDistance={28}
        minPolarAngle={0.08}
        maxPolarAngle={Math.PI - 0.08}
        // True 360° look-around of the suite + hallway beyond the glass.
        minAzimuthAngle={-Infinity}
        maxAzimuthAngle={Infinity}
        panSpeed={0.75}
        rotateSpeed={0.72}
        zoomSpeed={0.95}
      />
      <ambientLight intensity={0.55} color="#c8b8ff" />
      <directionalLight position={[1.5, 4.2, 2]} intensity={0.65} color="#f2e8ff" />
      <pointLight position={[-1.15, 3.15, 0.4]} intensity={0.75} color="#7ef9ff" distance={8} />
      <pointLight position={[1.15, 3.15, 0.4]} intensity={0.75} color="#b967ff" distance={8} />
      <pointLight position={[0, 1.9, -2.4]} intensity={0.55} color="#2de2e6" distance={7} />
      <pointLight position={[0, 5.5, -10]} intensity={0.7} color="#9ecbff" distance={14} />
      <pointLight position={[-5.5, 2.4, 2.2]} intensity={0.4} color="#b967ff" distance={7} />
      <pointLight position={[5.2, 2.2, 1.5]} intensity={0.4} color="#7ef9ff" distance={7} />

      <OfficeFloor />
      <Ceiling />
      <SideWall x={-7.9} rot={Math.PI / 2} />
      <SideWall x={7.9} rot={-Math.PI / 2} />
      <WallStockChart bot={bot} desk={desk} side="left" />
      <WallStockChart bot={bot} desk={desk} side="right" />
      <Door />
      <Credenza />
      <RoomDressing />
      <WindowWall />
      <StreetCity bots={bots && bots.length ? bots : [bot]} desk={desk} />
      <Desk />
      <DeskKit />
      <OfficeChair />

      <MonitorFrame position={[-1.55, 1.28, -0.62]} rotation={[0, 0.22, 0]} size={[1.02, 0.64]} edge="#39ff14" map={maps.left} onOpen={onOpenScreens} />
      <MonitorFrame position={[0.02, 1.4, -0.88]} rotation={[-0.08, 0, 0]} size={[1.22, 0.72]} edge="#2de2e6" map={maps.center} onOpen={onOpenScreens} />
      <MonitorFrame position={[1.58, 1.28, -0.62]} rotation={[0, -0.22, 0]} size={[1.02, 0.64]} edge="#39ff14" map={maps.right} onOpen={onOpenScreens} />

      <BotFigure pose={pose} deskWork />

      <OfficeFloorPlan
        bots={bots && bots.length ? bots : [bot]}
        desk={desk}
        activeId={bot.id}
        doorOpen={doorOpen}
        onToggleDoor={() => setDoorOpen((v) => !v)}
        onEnterHall={() => {
          onEnterHall?.()
        }}
        onEnterBoss={() => {
          onEnterBoss?.()
        }}
        onEnterSuite={(id) => onSelectBot?.(id)}
      />
      <NeonBloom strength={0.58} />
    </>
  )
}
