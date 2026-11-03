import { useMemo } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { DoubleSide } from 'three'
import type { BotRow, Desk } from '../types'
import { beamColorFor } from '../data/format'
import { activeWingRooms, type WingRoom } from '../data/officeWingLayout'
import { ROOM_HALF_D, ROOM_HALF_W, WING_HALL } from '../data/wingWalk'
import { NeonBloom } from './Effects'
import { OfficeInterior } from './OfficeScene'
import { WingWalker } from './WingWalker'

type Props = {
  bot: BotRow
  bots: BotRow[]
  desk?: Desk
  /** Tower we entered from — walker spawns behind this bot once. */
  spawnBotId: string
  /** Proximity room change (does not re-spawn the walker). */
  onSelect: (id: string) => void
  onOpenScreens?: () => void
}

const WALL_H = WING_HALL.wallH
const SUITE_SCALE = 0.62
const DOOR_W = 2.1

function HallCosmetics() {
  const x0 = (WING_HALL.xMin + WING_HALL.xMax) / 2
  const len = WING_HALL.xMax - WING_HALL.xMin
  const width = WING_HALL.zMax - WING_HALL.zMin
  return (
    <group>
      {/* Continuous hall slab */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[x0, 0, 0]} receiveShadow={false}>
        <planeGeometry args={[len + 0.4, width + 0.2]} />
        <meshStandardMaterial color="#0c0818" roughness={0.78} metalness={0.14} side={DoubleSide} />
      </mesh>
      {/* Neon runner */}
      <mesh position={[x0, 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[len - 0.6, 0.42]} />
        <meshStandardMaterial color="#152238" emissive="#2de2e6" emissiveIntensity={0.22} roughness={0.55} />
      </mesh>
      {/* Side baseboards */}
      {([-1, 1] as const).map((s) => (
        <mesh key={s} position={[x0, 0.08, s * (width / 2 - 0.04)]}>
          <boxGeometry args={[len, 0.16, 0.06]} />
          <meshStandardMaterial color="#7ec8d8" metalness={0.35} roughness={0.4} />
        </mesh>
      ))}
      {/* Ceiling + troffers */}
      <mesh position={[x0, WALL_H, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[len + 0.4, width + 0.2]} />
        <meshStandardMaterial color="#161028" roughness={0.9} side={DoubleSide} />
      </mesh>
      {[4, 10, 16, 22, 28].map((x) => (
        <group key={x}>
          <mesh position={[x, WALL_H - 0.05, 0]}>
            <boxGeometry args={[1.8, 0.06, 0.38]} />
            <meshBasicMaterial color="#e8f7ff" toneMapped={false} />
          </mesh>
          <pointLight position={[x, WALL_H - 0.35, 0]} intensity={0.35} color="#dff6ff" distance={7} />
        </group>
      ))}
      {/* Entry arch */}
      <group position={[WING_HALL.xMin + 0.2, 0, 0]}>
        <mesh position={[0, WALL_H / 2, 0]}>
          <boxGeometry args={[0.18, WALL_H, width + 0.35]} />
          <meshStandardMaterial color="#1a2130" metalness={0.4} roughness={0.4} />
        </mesh>
        <mesh position={[0.2, 2.55, 0]}>
          <boxGeometry args={[0.08, 0.28, 1.6]} />
          <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={0.65} />
        </mesh>
        {/* Welcome kiosk */}
        <mesh position={[1.1, 0.55, 0]}>
          <boxGeometry args={[0.35, 1.1, 0.55]} />
          <meshStandardMaterial color="#121820" metalness={0.35} roughness={0.45} />
        </mesh>
        <mesh position={[1.1, 1.2, 0.02]}>
          <boxGeometry args={[0.28, 0.22, 0.04]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
      </group>
      {/* Lounge nooks between door pairs */}
      {[8, 16].map((x) => (
        <group key={`lounge-${x}`} position={[x, 0, 0]}>
          <mesh position={[0, 0.28, 0]}>
            <boxGeometry args={[1.4, 0.55, 0.7]} />
            <meshStandardMaterial color="#1a1030" roughness={0.7} />
          </mesh>
          <mesh position={[-0.55, 0.55, 0]}>
            <cylinderGeometry args={[0.08, 0.1, 0.9, 10]} />
            <meshStandardMaterial color="#1d6b45" roughness={0.65} />
          </mesh>
          <mesh position={[-0.55, 1.05, 0]}>
            <sphereGeometry args={[0.22, 10, 10]} />
            <meshStandardMaterial color="#2a8f5a" roughness={0.7} />
          </mesh>
          <pointLight position={[0, 1.4, 0]} intensity={0.25} color="#b967ff" distance={4} />
        </group>
      ))}
      {/* Water cooler near boss end */}
      <group position={[26.2, 0, 0.95]}>
        <mesh position={[0, 0.55, 0]}>
          <cylinderGeometry args={[0.18, 0.2, 1.1, 12]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.55} roughness={0.3} />
        </mesh>
        <mesh position={[0, 1.25, 0]}>
          <sphereGeometry args={[0.22, 12, 12]} />
          <meshStandardMaterial color="#7ef9ff" transparent opacity={0.55} roughness={0.2} />
        </mesh>
      </group>
    </group>
  )
}

function SuiteShell({ room, color, live }: { room: WingRoom; color: string; live: boolean }) {
  const doorGap = DOOR_W
  const wallSeg = (ROOM_HALF_W * 2 - doorGap) / 2
  return (
    <group position={room.position} rotation={[0, room.yaw, 0]}>
      {/* Floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <planeGeometry args={[ROOM_HALF_W * 2, ROOM_HALF_D * 2]} />
        <meshStandardMaterial
          color={room.boss ? '#1a1230' : '#12082a'}
          roughness={0.72}
          metalness={0.1}
          side={DoubleSide}
        />
      </mesh>
      {/* Accent rug */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, -0.4]}>
        <circleGeometry args={[1.35, 24]} />
        <meshStandardMaterial color="#1a1038" emissive={color} emissiveIntensity={0.08} roughness={0.9} />
      </mesh>
      {/* Side walls */}
      {([-ROOM_HALF_W, ROOM_HALF_W] as const).map((x) => (
        <mesh key={`sx-${x}`} position={[x, WALL_H / 2, 0]}>
          <boxGeometry args={[0.12, WALL_H, ROOM_HALF_D * 2]} />
          <meshStandardMaterial color="#241848" roughness={0.88} />
        </mesh>
      ))}
      {/* Window wall */}
      <mesh position={[0, WALL_H / 2, -ROOM_HALF_D]}>
        <boxGeometry args={[ROOM_HALF_W * 2, WALL_H, 0.12]} />
        <meshStandardMaterial color="#241848" roughness={0.88} />
      </mesh>
      {/* Fake window glow */}
      <mesh position={[0, 1.7, -ROOM_HALF_D + 0.08]}>
        <planeGeometry args={[ROOM_HALF_W * 1.15, 1.8]} />
        <meshBasicMaterial color="#7ef9ff" transparent opacity={0.08} toneMapped={false} />
      </mesh>
      {/* Hall wall with OPEN doorway (walk through — no click teleport) */}
      <mesh position={[-(doorGap / 2 + wallSeg / 2), WALL_H / 2, ROOM_HALF_D]}>
        <boxGeometry args={[wallSeg, WALL_H, 0.12]} />
        <meshStandardMaterial color="#1b2130" roughness={0.85} />
      </mesh>
      <mesh position={[doorGap / 2 + wallSeg / 2, WALL_H / 2, ROOM_HALF_D]}>
        <boxGeometry args={[wallSeg, WALL_H, 0.12]} />
        <meshStandardMaterial color="#1b2130" roughness={0.85} />
      </mesh>
      {/* Door frame glow */}
      {([-doorGap / 2, doorGap / 2] as const).map((x) => (
        <mesh key={`df-${x}`} position={[x, 1.15, ROOM_HALF_D]}>
          <boxGeometry args={[0.06, 2.3, 0.08]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.55} />
        </mesh>
      ))}
      <mesh position={[0, 2.35, ROOM_HALF_D]}>
        <boxGeometry args={[doorGap + 0.08, 0.08, 0.08]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.55} />
      </mesh>
      {/* Name plate beside door */}
      <mesh position={[doorGap / 2 + 0.55, 1.85, ROOM_HALF_D + 0.05]}>
        <boxGeometry args={[0.7, 0.28, 0.04]} />
        <meshStandardMaterial color="#10141c" metalness={0.35} roughness={0.4} />
      </mesh>
      <mesh position={[doorGap / 2 + 0.55, 1.85, ROOM_HALF_D + 0.08]}>
        <boxGeometry args={[0.55, 0.12, 0.02]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      {room.boss && (
        <mesh position={[0, 2.7, ROOM_HALF_D + 0.06]}>
          <boxGeometry args={[0.9, 0.16, 0.04]} />
          <meshBasicMaterial color="#f9c80e" toneMapped={false} />
        </mesh>
      )}
      {/* Dim desk when not the live suite */}
      {!live && (
        <group position={[0, 0, -0.35]}>
          <mesh position={[0, 0.76, 0]}>
            <boxGeometry args={[2.6, 0.08, 1.05]} />
            <meshStandardMaterial color="#12151c" metalness={0.3} roughness={0.5} />
          </mesh>
          <mesh position={[0, 1.15, -0.4]}>
            <boxGeometry args={[1.5, 0.65, 0.05]} />
            <meshStandardMaterial color="#0c1018" emissive={color} emissiveIntensity={0.22} />
          </mesh>
          <mesh position={[0, 0.55, 0.7]}>
            <boxGeometry args={[0.55, 0.7, 0.55]} />
            <meshStandardMaterial color="#1c2433" roughness={0.6} />
          </mesh>
        </group>
      )}
      {/* Fun bits: plant + shelf */}
      <mesh position={[-ROOM_HALF_W + 0.55, 0.35, -ROOM_HALF_D + 0.7]}>
        <cylinderGeometry args={[0.12, 0.14, 0.7, 10]} />
        <meshStandardMaterial color="#1d6b45" roughness={0.65} />
      </mesh>
      <mesh position={[-ROOM_HALF_W + 0.55, 0.85, -ROOM_HALF_D + 0.7]}>
        <sphereGeometry args={[0.28, 10, 10]} />
        <meshStandardMaterial color="#2a8f5a" roughness={0.7} />
      </mesh>
      <mesh position={[ROOM_HALF_W - 0.45, 1.1, -0.2]}>
        <boxGeometry args={[0.35, 1.6, 0.9]} />
        <meshStandardMaterial color="#161b26" roughness={0.55} />
      </mesh>
      <pointLight position={[0, 2.6, 0]} intensity={live ? 0.45 : 0.2} color={color} distance={6} />
    </group>
  )
}

/**
 * Continuous walkable trading wing — hallway + open suites + boss.
 * Spawn behind the focused tower bot; WASD walks the whole floor (no room-click teleport).
 */
export function OfficeHallScene({ bot, bots, desk, spawnBotId, onSelect, onOpenScreens }: Props) {
  const rooms = useMemo(() => activeWingRooms(), [])

  return (
    <>
      <color attach="background" args={['#070412']} />
      <fog attach="fog" args={['#070412', 18, 55]} />
      <PerspectiveCamera makeDefault fov={55} near={0.08} far={120} position={[4, 1.8, 2]} />
      <ambientLight intensity={0.48} color="#c8b8ff" />
      <directionalLight position={[10, 18, 8]} intensity={0.45} color="#f2e8ff" />

      <HallCosmetics />

      {rooms.map((room, i) => {
        const color = beamColorFor(room.botId, i)
        const live = room.botId === bot.id
        return <SuiteShell key={room.id} room={room} color={color} live={live} />
      })}

      {/* Live desk kit for the suite you're currently in */}
      {rooms.map((room) => {
        if (room.botId !== bot.id) return null
        const row = bots.find((b) => b.id === room.botId) || bot
        return (
          <group key={`live-${room.id}`} position={room.position} rotation={[0, room.yaw, 0]} scale={SUITE_SCALE}>
            <OfficeInterior bot={row} bots={bots} desk={desk} onOpenScreens={onOpenScreens} />
          </group>
        )
      })}

      <WingWalker
        active
        focusBotId={spawnBotId}
        onEnterRoom={(id) => {
          if (id !== bot.id) onSelect(id)
        }}
      />

      <NeonBloom strength={0.34} />
    </>
  )
}
