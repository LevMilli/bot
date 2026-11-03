import { DoubleSide } from 'three'
import type { BotRow, Desk } from '../types'
import { BotFigure } from './BotFigure'
import { botPose } from '../data/botPose'
import { beamColorFor } from '../data/format'

const HALL_Z0 = 5.15
const HALL_Z1 = 22
const HALL_W = 3.6
const ACCENT = '#2de2e6'
const WALL = '#1a1230'
const FLOOR = '#0a0614'

function HallLight({ z }: { z: number }) {
  return (
    <group position={[0, 3.15, z]}>
      <mesh>
        <boxGeometry args={[0.55, 0.05, 0.55]} />
        <meshBasicMaterial color="#e7f6ff" toneMapped={false} />
      </mesh>
      <pointLight intensity={0.35} color="#c8e8ff" distance={6} />
    </group>
  )
}

/** Slim sister suite — same theme, slight prop differences per bot index. */
function NeighborSuite({
  bot,
  index,
  position,
  rotationY,
  active,
  onEnter,
}: {
  bot: BotRow
  index: number
  position: [number, number, number]
  rotationY: number
  active?: boolean
  onEnter?: () => void
}) {
  const accent = beamColorFor(bot.id, index)
  const pose = botPose(bot)
  const deskTint = index % 2 === 0 ? '#16345e' : '#1a2860'
  const hasLamp = index % 3 !== 1
  const hasMug = index % 2 === 0
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      {/* Hollow shell — open toward the hallway (+Z) */}
      <mesh position={[0, 1.55, -2.15]}>
        <boxGeometry args={[5.2, 3.1, 0.12]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      {([-2.55, 2.55] as const).map((x) => (
        <mesh key={x} position={[x, 1.55, 0]}>
          <boxGeometry args={[0.12, 3.1, 4.4]} />
          <meshStandardMaterial color={WALL} roughness={0.9} />
        </mesh>
      ))}
      <mesh position={[0, 3.12, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[5.2, 4.4]} />
        <meshStandardMaterial color="#12081f" roughness={0.9} side={DoubleSide} />
      </mesh>
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[5.0, 4.2]} />
        <meshStandardMaterial color={FLOOR} roughness={0.75} metalness={0.12} />
      </mesh>
      <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[4.6, 3.8]} />
        <meshBasicMaterial color={accent} transparent opacity={0.04} toneMapped={false} />
      </mesh>
      {/* glass door into hall */}
      <mesh
        position={[0, 1.35, 2.22]}
        onClick={(e) => {
          e.stopPropagation()
          onEnter?.()
        }}
        onPointerOver={() => {
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[1.35, 2.35, 0.06]} />
        <meshPhysicalMaterial
          color="#9fdfff"
          transparent
          opacity={0.18}
          roughness={0.08}
          metalness={0.2}
          transmission={0.55}
          thickness={0.2}
          toneMapped={false}
        />
      </mesh>
      <mesh position={[0, 2.65, 2.24]}>
        <boxGeometry args={[1.5, 0.12, 0.08]} />
        <meshBasicMaterial color={accent} toneMapped={false} />
      </mesh>
      {/* mini desk */}
      <mesh position={[0, 0.72, -0.35]}>
        <boxGeometry args={[2.4, 0.07, 1.05]} />
        <meshStandardMaterial color={deskTint} metalness={0.4} roughness={0.4} />
      </mesh>
      {([-0.7, 0, 0.7] as const).map((x) => (
        <mesh key={x} position={[x, 1.15, -0.7]} rotation={[0, x * 0.12, 0]}>
          <boxGeometry args={[0.55, 0.38, 0.04]} />
          <meshStandardMaterial color="#0c1018" metalness={0.4} roughness={0.4} />
        </mesh>
      ))}
      {hasLamp && (
        <mesh position={[0.55, 0.95, -0.15]}>
          <coneGeometry args={[0.07, 0.1, 12, 1, true]} />
          <meshStandardMaterial color="#f4e2a8" emissive="#f9c80e" emissiveIntensity={0.5} side={DoubleSide} />
        </mesh>
      )}
      {hasMug && (
        <mesh position={[-0.55, 0.84, 0.05]}>
          <cylinderGeometry args={[0.04, 0.035, 0.07, 12]} />
          <meshStandardMaterial color="#101820" roughness={0.45} />
        </mesh>
      )}
      <mesh position={[0, 0.55, 0.55]}>
        <boxGeometry args={[0.48, 0.08, 0.42]} />
        <meshStandardMaterial color="#12151c" roughness={0.7} />
      </mesh>
      <group position={[0, 0.35, 0.55]} scale={0.82}>
        <BotFigure pose={pose} seated />
      </group>
      {/* name plate */}
      <mesh position={[0, 2.85, 2.1]}>
        <boxGeometry args={[1.6, 0.22, 0.04]} />
        <meshStandardMaterial color="#0a0c12" metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, 2.85, 2.13]}>
        <boxGeometry args={[1.45, 0.12, 0.02]} />
        <meshBasicMaterial color={active ? '#f9c80e' : accent} toneMapped={false} />
      </mesh>
    </group>
  )
}

function BossSuite({
  onEnter,
}: {
  onEnter?: () => void
}) {
  return (
    <group position={[0, 0, HALL_Z1 + 4.2]}>
      {/* Hollow boss chamber — open toward hallway (-Z) */}
      <mesh position={[0, 1.7, 3.5]}>
        <boxGeometry args={[8.5, 3.4, 0.14]} />
        <meshStandardMaterial color="#140a28" roughness={0.88} />
      </mesh>
      {([-4.2, 4.2] as const).map((x) => (
        <mesh key={x} position={[x, 1.7, 0]}>
          <boxGeometry args={[0.14, 3.4, 7.2]} />
          <meshStandardMaterial color="#140a28" roughness={0.88} />
        </mesh>
      ))}
      <mesh position={[0, 3.35, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[8.5, 7.2]} />
        <meshStandardMaterial color="#10061c" roughness={0.9} side={DoubleSide} />
      </mesh>
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[8.2, 6.9]} />
        <meshStandardMaterial color="#080412" roughness={0.7} metalness={0.15} />
      </mesh>
      {/* glass entry from hall */}
      <mesh
        position={[0, 1.45, -3.55]}
        onClick={(e) => {
          e.stopPropagation()
          onEnter?.()
        }}
        onPointerOver={() => {
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[2.2, 2.6, 0.08]} />
        <meshPhysicalMaterial
          color="#b7fff8"
          transparent
          opacity={0.22}
          roughness={0.06}
          metalness={0.15}
          transmission={0.6}
          thickness={0.25}
          toneMapped={false}
        />
      </mesh>
      <mesh position={[0, 2.9, -3.52]}>
        <boxGeometry args={[2.6, 0.18, 0.1]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      {/* boss desk + wall board bank */}
      <mesh position={[0, 0.78, 1.1]}>
        <boxGeometry args={[3.8, 0.1, 1.4]} />
        <meshStandardMaterial color="#1a3a68" metalness={0.45} roughness={0.35} />
      </mesh>
      {([-1.4, -0.7, 0, 0.7, 1.4] as const).map((x) => (
        <mesh key={x} position={[x, 2.05, 2.9]}>
          <boxGeometry args={[0.95, 0.7, 0.05]} />
          <meshStandardMaterial color="#0c1018" metalness={0.4} roughness={0.4} />
        </mesh>
      ))}
      {([-1.4, -0.7, 0, 0.7, 1.4] as const).map((x, i) => (
        <mesh key={`g-${x}`} position={[x, 2.05, 2.94]}>
          <planeGeometry args={[0.82, 0.55]} />
          <meshBasicMaterial
            color={i === 2 ? '#2de2e6' : i % 2 ? '#39ff14' : '#b967ff'}
            transparent
            opacity={0.35}
            toneMapped={false}
          />
        </mesh>
      ))}
      <mesh position={[0, 2.55, -3.4]}>
        <boxGeometry args={[2.4, 0.28, 0.06]} />
        <meshStandardMaterial color="#0a0c12" />
      </mesh>
      <mesh position={[0, 2.55, -3.36]}>
        <boxGeometry args={[2.1, 0.16, 0.03]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <pointLight position={[0, 2.8, 0]} intensity={0.55} color="#f9c80e" distance={9} />
      <pointLight position={[0, 2.2, 2.2]} intensity={0.4} color="#2de2e6" distance={7} />
    </group>
  )
}

type Props = {
  bots: BotRow[]
  desk?: Desk
  activeId: string
  doorOpen: boolean
  onToggleDoor?: () => void
  onEnterHall?: () => void
  onEnterBoss?: () => void
  onEnterSuite?: (id: string) => void
}

/**
 * Hallway + five themed suites + boss chamber beyond the home office glass wall.
 * Home suite stays in OfficeScene; this module only builds what is behind the glass.
 */
export function OfficeFloorPlan({
  bots,
  desk: _desk,
  activeId,
  doorOpen,
  onToggleDoor,
  onEnterHall,
  onEnterBoss,
  onEnterSuite,
}: Props) {
  const ordered = bots.length ? bots : []
  // Other suites line the hall; active bot stays in the home room.
  const others = ordered.filter((b) => b.id !== activeId)
  const hallSlots: { bot: BotRow; index: number; pos: [number, number, number]; rot: number }[] = []
  const leftZs = [8.5, 13.5]
  const rightZs = [8.5, 13.5, 18.2]
  others.forEach((bot, i) => {
    const globalIndex = ordered.findIndex((b) => b.id === bot.id)
    if (i < 2) {
      hallSlots.push({
        bot,
        index: globalIndex < 0 ? i : globalIndex,
        pos: [-(HALL_W / 2 + 2.7), 0, leftZs[i] ?? 8.5],
        rot: Math.PI / 2,
      })
    } else {
      const ri = i - 2
      hallSlots.push({
        bot,
        index: globalIndex < 0 ? i : globalIndex,
        pos: [HALL_W / 2 + 2.7, 0, rightZs[ri] ?? 18.2],
        rot: -Math.PI / 2,
      })
    }
  })

  return (
    <group>
      {/* Glass curtain wall on the home office back face */}
      <group position={[0, 0, 4.78]}>
        {/* opaque side panels */}
        <mesh position={[-4.6, 1.7, 0]}>
          <boxGeometry args={[5.2, 3.4, 0.12]} />
          <meshStandardMaterial color="#160e2c" roughness={0.9} />
        </mesh>
        <mesh position={[4.6, 1.7, 0]}>
          <boxGeometry args={[5.2, 3.4, 0.12]} />
          <meshStandardMaterial color="#160e2c" roughness={0.9} />
        </mesh>
        {/* glass panes */}
        {([-2.15, 2.15] as const).map((x) => (
          <mesh key={x} position={[x, 1.85, 0.02]} raycast={() => null}>
            <planeGeometry args={[2.5, 2.5]} />
            <meshPhysicalMaterial
              color="#b7fff8"
              transparent
              opacity={0.12}
              roughness={0.05}
              metalness={0.1}
              transmission={0.7}
              thickness={0.3}
              side={DoubleSide}
              toneMapped={false}
            />
          </mesh>
        ))}
        {/* mullions */}
        {([-3.4, -0.95, 0.95, 3.4] as const).map((x) => (
          <mesh key={x} position={[x, 1.85, 0.04]}>
            <boxGeometry args={[0.07, 2.6, 0.08]} />
            <meshStandardMaterial color="#3a2a68" metalness={0.55} roughness={0.35} />
          </mesh>
        ))}
        <mesh position={[0, 3.2, 0.04]}>
          <boxGeometry args={[8.2, 0.08, 0.08]} />
          <meshStandardMaterial color="#3a2a68" metalness={0.55} roughness={0.35} />
        </mesh>
        <mesh position={[0, 0.55, 0.04]}>
          <boxGeometry args={[8.2, 0.1, 0.1]} />
          <meshStandardMaterial color="#1b212e" roughness={0.7} />
        </mesh>

        {/* Sliding glass door — click to open onto the floor plan */}
        <group
          position={[doorOpen ? -1.35 : 0, 1.4, 0.08]}
          onClick={(e) => {
            e.stopPropagation()
            onToggleDoor?.()
            if (!doorOpen) onEnterHall?.()
          }}
          onPointerOver={() => {
            document.body.style.cursor = 'pointer'
          }}
          onPointerOut={() => {
            document.body.style.cursor = 'default'
          }}
        >
          <mesh>
            <boxGeometry args={[1.55, 2.45, 0.05]} />
            <meshPhysicalMaterial
              color="#9fdfff"
              transparent
              opacity={0.28}
              roughness={0.06}
              metalness={0.2}
              transmission={0.55}
              thickness={0.2}
              toneMapped={false}
            />
          </mesh>
          <mesh position={[0.55, 0, 0.04]}>
            <boxGeometry args={[0.04, 0.28, 0.04]} />
            <meshStandardMaterial color="#c5ccd8" metalness={0.85} roughness={0.2} />
          </mesh>
          <mesh position={[0, 1.35, 0.03]}>
            <boxGeometry args={[1.4, 0.08, 0.04]} />
            <meshBasicMaterial color="#2de2e6" toneMapped={false} />
          </mesh>
        </group>
        {/* door frame */}
        <mesh position={[0, 2.7, 0.06]}>
          <boxGeometry args={[1.75, 0.1, 0.1]} />
          <meshStandardMaterial color="#7ec8d8" metalness={0.4} roughness={0.4} />
        </mesh>
        {([-0.85, 0.85] as const).map((x) => (
          <mesh key={x} position={[x, 1.4, 0.06]}>
            <boxGeometry args={[0.08, 2.55, 0.1]} />
            <meshStandardMaterial color="#7ec8d8" metalness={0.4} roughness={0.4} />
          </mesh>
        ))}
      </group>

      {/* Hallway corridor */}
      <mesh position={[0, 0.01, (HALL_Z0 + HALL_Z1) / 2]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[HALL_W + 0.4, HALL_Z1 - HALL_Z0 + 1]} />
        <meshStandardMaterial color="#0c0818" roughness={0.65} metalness={0.2} />
      </mesh>
      <mesh position={[0, 0.025, (HALL_Z0 + HALL_Z1) / 2]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.1, HALL_Z1 - HALL_Z0]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.07} toneMapped={false} />
      </mesh>
      {([-HALL_W / 2 - 0.05, HALL_W / 2 + 0.05] as const).map((x) => (
        <mesh key={x} position={[x, 1.6, (HALL_Z0 + HALL_Z1) / 2]}>
          <boxGeometry args={[0.12, 3.2, HALL_Z1 - HALL_Z0 + 0.8]} />
          <meshStandardMaterial color="#1a1230" roughness={0.88} />
        </mesh>
      ))}
      <mesh position={[0, 3.25, (HALL_Z0 + HALL_Z1) / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[HALL_W + 0.6, HALL_Z1 - HALL_Z0 + 1]} />
        <meshStandardMaterial color="#12081f" roughness={0.9} side={DoubleSide} />
      </mesh>
      {[7, 10.5, 14, 17.5, 20.5].map((z) => (
        <HallLight key={z} z={z} />
      ))}
      {/* floor LEDs */}
      {[7, 11, 15, 19].map((z) => (
        <mesh key={`led-${z}`} position={[0, 0.04, z]}>
          <boxGeometry args={[0.35, 0.02, 0.08]} />
          <meshBasicMaterial color="#b967ff" toneMapped={false} />
        </mesh>
      ))}

      {hallSlots.map((slot) => (
        <NeighborSuite
          key={slot.bot.id}
          bot={slot.bot}
          index={slot.index}
          position={slot.pos}
          rotationY={slot.rot}
          active={slot.bot.id === activeId}
          onEnter={() => onEnterSuite?.(slot.bot.id)}
        />
      ))}

      <BossSuite onEnter={onEnterBoss} />

      {/* subtle hall fog fill light */}
      <pointLight position={[0, 2.4, 14]} intensity={0.45} color="#9ecbff" distance={18} />
    </group>
  )
}
