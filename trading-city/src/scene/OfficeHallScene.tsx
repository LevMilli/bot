import { useEffect, useMemo, useRef } from 'react'
import { OrbitControls, PerspectiveCamera } from '@react-three/drei'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { DoubleSide } from 'three'
import type { BotRow, Desk } from '../types'
import { beamColorFor } from '../data/format'
import { activeWingRooms, type WingRoom } from '../data/officeWingLayout'
import { NeonBloom } from './Effects'
import { OfficeInterior } from './OfficeScene'

type Props = {
  bot: BotRow
  bots: BotRow[]
  desk?: Desk
  hallView: boolean
  onSelect: (id: string) => void
  onOpenScreens?: () => void
}

const HALL_LEN = 32
const HALL_W = 3.6
const ROOM_W = 10.5
const ROOM_D = 8.2
const WALL_H = 3.4
const SUITE_SCALE = 0.62

/** Map a local office-suite point into wing world space. */
function suiteWorld(room: WingRoom, local: [number, number, number]): [number, number, number] {
  const [lx, ly, lz] = local
  const s = SUITE_SCALE
  const c = Math.cos(room.yaw)
  const sn = Math.sin(room.yaw)
  return [
    room.position[0] + c * lx * s + sn * lz * s,
    room.position[1] + ly * s,
    room.position[2] - sn * lx * s + c * lz * s,
  ]
}

function HallShell() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[HALL_LEN / 2 - 1.5, 0, 0]}>
        <planeGeometry args={[HALL_LEN + 4, HALL_W + 0.4]} />
        <meshStandardMaterial color="#0e0a1c" roughness={0.78} metalness={0.12} side={DoubleSide} />
      </mesh>
      <mesh position={[HALL_LEN / 2 - 1.5, WALL_H, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[HALL_LEN + 4, HALL_W + 0.4]} />
        <meshStandardMaterial color="#18122c" roughness={0.9} side={DoubleSide} />
      </mesh>
      <mesh position={[HALL_LEN / 2 - 1.5, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[HALL_LEN, 0.55]} />
        <meshStandardMaterial
          color="#1a2744"
          emissive="#2de2e6"
          emissiveIntensity={0.18}
          roughness={0.65}
          metalness={0.2}
        />
      </mesh>
      {[4, 12, 20, 28].map((x) => (
        <mesh key={x} position={[x, WALL_H - 0.04, 0]}>
          <boxGeometry args={[1.6, 0.05, 0.35]} />
          <meshBasicMaterial color="#e7f6ff" toneMapped={false} />
        </mesh>
      ))}
      <group position={[-1.2, 1.6, 0]}>
        <mesh>
          <boxGeometry args={[0.12, 2.6, HALL_W + 0.2]} />
          <meshStandardMaterial color="#1a2130" metalness={0.35} roughness={0.45} />
        </mesh>
        <mesh position={[0.18, 0.95, 0]}>
          <boxGeometry args={[0.04, 0.35, 1.8]} />
          <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={0.55} />
        </mesh>
      </group>
    </group>
  )
}

function DoorPlaque({
  color,
  label,
  boss,
  active,
  onSelect,
}: {
  color: string
  label: string
  boss?: boolean
  active: boolean
  onSelect: () => void
}) {
  return (
    <group position={[0, 1.15, ROOM_D / 2 - 0.05]}>
      <mesh
        onClick={(e) => {
          e.stopPropagation()
          onSelect()
        }}
        onPointerOver={() => {
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[1.35, 2.35, 0.1]} />
        <meshStandardMaterial
          color={active ? '#0e1828' : '#0c1018'}
          emissive={color}
          emissiveIntensity={active ? 0.55 : 0.22}
          metalness={0.35}
          roughness={0.45}
        />
      </mesh>
      {/* Name stripe — no Text/font loader (keeps WebGL stable). */}
      <mesh position={[0, 1.35, 0.08]}>
        <boxGeometry args={[1.15, 0.22, 0.04]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.95, 0.08]}>
        <boxGeometry args={[0.95, 0.08, 0.03]} />
        <meshBasicMaterial color="#f4f7ff" toneMapped={false} />
      </mesh>
      {boss && (
        <mesh position={[0, -0.95, 0.08]}>
          <boxGeometry args={[0.7, 0.12, 0.03]} />
          <meshBasicMaterial color="#f9c80e" toneMapped={false} />
        </mesh>
      )}
      {/* Tiny label helper for a11y via title is HUD-side; keep mesh lean. */}
      <group visible={false}>{label}</group>
    </group>
  )
}

function RoomShell({
  room,
  color,
  active,
  onSelect,
}: {
  room: WingRoom
  color: string
  active: boolean
  onSelect: () => void
}) {
  return (
    <group position={room.position} rotation={[0, room.yaw, 0]}>
      {!active && (
        <>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
            <planeGeometry args={[ROOM_W, ROOM_D]} />
            <meshStandardMaterial
              color={room.boss ? '#1a1230' : '#12082a'}
              roughness={0.72}
              metalness={0.1}
              side={DoubleSide}
            />
          </mesh>
          {([-ROOM_W / 2, ROOM_W / 2] as const).map((x) => (
            <mesh key={`sx-${x}`} position={[x, WALL_H / 2, 0]}>
              <boxGeometry args={[0.12, WALL_H, ROOM_D]} />
              <meshStandardMaterial color="#241848" roughness={0.88} />
            </mesh>
          ))}
          <mesh position={[0, WALL_H / 2, -ROOM_D / 2]}>
            <boxGeometry args={[ROOM_W, WALL_H, 0.12]} />
            <meshStandardMaterial color="#241848" roughness={0.88} />
          </mesh>
          <mesh position={[-ROOM_W * 0.28, WALL_H / 2, ROOM_D / 2]}>
            <boxGeometry args={[ROOM_W * 0.42, WALL_H, 0.12]} />
            <meshStandardMaterial color="#1b2130" roughness={0.85} />
          </mesh>
          <mesh position={[ROOM_W * 0.28, WALL_H / 2, ROOM_D / 2]}>
            <boxGeometry args={[ROOM_W * 0.42, WALL_H, 0.12]} />
            <meshStandardMaterial color="#1b2130" roughness={0.85} />
          </mesh>
          <group position={[0, 0, -0.6]}>
            <mesh position={[0, 0.76, 0]}>
              <boxGeometry args={[2.8, 0.08, 1.1]} />
              <meshStandardMaterial color="#12151c" metalness={0.3} roughness={0.5} />
            </mesh>
            <mesh position={[0, 1.2, -0.35]}>
              <boxGeometry args={[1.6, 0.7, 0.05]} />
              <meshStandardMaterial color="#0c1018" emissive={color} emissiveIntensity={0.25} />
            </mesh>
          </group>
        </>
      )}
      <DoorPlaque color={color} label={room.label} boss={room.boss} active={active} onSelect={onSelect} />
    </group>
  )
}

/**
 * Full trading-wing 3D model: hallway + five worker offices + boss suite.
 * Hall overview orbits the spine; focusing a room drops into that desk.
 */
export function OfficeHallScene({ bot, bots, desk, hallView, onSelect, onOpenScreens }: Props) {
  const controls = useRef<OrbitControlsImpl>(null)
  const rooms = useMemo(() => activeWingRooms(), [])
  const focus = useMemo(() => rooms.find((r) => r.botId === bot.id) || rooms[0], [rooms, bot.id])

  const hallCam: [number, number, number] = [14, 11.5, 16]
  const hallTarget: [number, number, number] = [14, 0.4, 0]
  // Match the classic office home camera, transformed into the focused suite.
  const focusCam = suiteWorld(focus, [0.15, 1.78, 3.35])
  const focusTarget = suiteWorld(focus, [0, 1.42, 0.05])

  useEffect(() => {
    const orbit = controls.current
    const cam = orbit?.object
    if (!orbit || !cam) return
    if (hallView) {
      cam.position.set(...hallCam)
      orbit.target.set(...hallTarget)
    } else {
      cam.position.set(...focusCam)
      orbit.target.set(...focusTarget)
    }
    orbit.update()
  }, [hallView, focus.botId, focusCam, focusTarget])

  return (
    <>
      <color attach="background" args={['#0a0618']} />
      <fog attach="fog" args={['#0a0618', hallView ? 28 : 14, hallView ? 70 : 36]} />
      <PerspectiveCamera makeDefault fov={hallView ? 48 : 46} near={0.08} far={120} position={hallView ? hallCam : focusCam} />
      <OrbitControls
        ref={controls}
        makeDefault
        target={hallView ? hallTarget : focusTarget}
        enableDamping
        dampingFactor={0.08}
        enablePan={hallView}
        minDistance={hallView ? 6 : 1.45}
        maxDistance={hallView ? 28 : 3.8}
        minPolarAngle={hallView ? 0.35 : 1.02}
        maxPolarAngle={hallView ? 1.35 : 1.75}
        minAzimuthAngle={hallView ? -Infinity : -1.4}
        maxAzimuthAngle={hallView ? Infinity : 1.4}
      />
      <ambientLight intensity={0.62} color="#c8b8ff" />
      <directionalLight position={[8, 16, 6]} intensity={0.6} color="#f2e8ff" />
      <pointLight position={[8, 3, 0]} intensity={0.55} color="#7ef9ff" distance={18} />
      <pointLight position={[22, 3, 0]} intensity={0.45} color="#b967ff" distance={16} />
      {!hallView && (
        <>
          <pointLight position={suiteWorld(focus, [-1.15, 3.15, 0.4])} intensity={0.85} color="#7ef9ff" distance={8} />
          <pointLight position={suiteWorld(focus, [1.15, 3.15, 0.4])} intensity={0.85} color="#b967ff" distance={8} />
          <pointLight position={suiteWorld(focus, [0, 1.9, -2.4])} intensity={0.65} color="#2de2e6" distance={7} />
        </>
      )}

      <HallShell />

      {rooms.map((room, i) => {
        const color = beamColorFor(room.botId, i)
        const active = !hallView && room.botId === bot.id
        return (
          <RoomShell
            key={room.id}
            room={room}
            color={color}
            active={active}
            onSelect={() => onSelect(room.botId)}
          />
        )
      })}

      {!hallView && (
        <group position={focus.position} rotation={[0, focus.yaw, 0]} scale={SUITE_SCALE}>
          <OfficeInterior bot={bot} bots={bots} desk={desk} onOpenScreens={onOpenScreens} />
        </group>
      )}

      <NeonBloom strength={hallView ? 0.32 : 0.45} />
    </>
  )
}
