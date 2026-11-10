import { useLayoutEffect, useMemo, useRef } from 'react'
import { Html, OrbitControls, PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { InstancedMesh } from 'three'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import type { BotRow } from '../types'
import { NeonBloom } from './Effects'

/** Seats on the Wall Street floor. Matches paper-bots HEADCOUNT. */
export const WALL_STREET_HEADCOUNT = 120

/** Six desks, twenty seats each. Colors are the pit bands. Jobs match the desk copy. */
export const FLOOR_DESKS = [
  { id: 'quote', name: 'Quote', seats: 20, color: '#3ddcff', job: 'No client flow arrives, so this desk does not quote.' },
  { id: 'research', name: 'Research', seats: 20, color: '#f4f0d4', job: 'Writes the skip in one sentence a person can check.' },
  { id: 'risk', name: 'Risk', seats: 20, color: '#ff4d6a', job: 'Holds the veto. A buy on this floor is a mistake.' },
  { id: 'ledger', name: 'Ledger', seats: 20, color: '#c6a15b', job: 'Cash stays at 0 and the position list stays empty.' },
  { id: 'control', name: 'Control', seats: 20, color: '#7aa2ff', job: 'Paper only. Keeps a key off this floor.' },
  { id: 'book', name: 'The book', seats: 20, color: '#39ff14', job: 'The only book on the floor, and it stays flat.' },
] as const

const ROWS = 12
const PER_SIDE = 5
const X_GAP = 0.78
const Z_GAP = 0.84
const AISLE = 1.45

type Seat = { x: number; z: number; suit: string; screen: string; desk: number }

const SUITS = ['#1b2a4a', '#243044', '#2a241c', '#1a1c24', '#3a2c24', '#15283a']

function buildSeats(): Seat[] {
  const seats: Seat[] = []
  let i = 0
  for (let r = 0; r < ROWS; r++) {
    const z = (r - (ROWS - 1) / 2) * Z_GAP
    const desk = Math.floor(r / 2)
    for (let side = 0; side < 2; side++) {
      for (let c = 0; c < PER_SIDE; c++) {
        const x = (side === 0 ? -1 : 1) * (AISLE + c * X_GAP)
        seats.push({
          x,
          z,
          suit: SUITS[(i + desk) % SUITS.length],
          screen: FLOOR_DESKS[desk].color,
          desk,
        })
        i += 1
      }
    }
  }
  return seats
}

const SEATS = buildSeats()

function bandZ(desk: number) {
  const r0 = desk * 2
  const z0 = (r0 - (ROWS - 1) / 2) * Z_GAP
  const z1 = (r0 + 1 - (ROWS - 1) / 2) * Z_GAP
  return (z0 + z1) / 2
}

function paint(mesh: InstancedMesh, colorOf: (seat: Seat, index: number) => string) {
  for (let i = 0; i < SEATS.length; i++) {
    mesh.setColorAt(i, new THREE.Color(colorOf(SEATS[i], i)))
  }
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
}

/**
 * The Wall Street tower interior: six desks, 120 staff, one book.
 * Staff are instanced. They do not place trades.
 */
export function WallStreetScene({ bot }: { bot: BotRow }) {
  const head = bot.traders && bot.traders >= 100 ? bot.traders : WALL_STREET_HEADCOUNT
  const desks = useRef<InstancedMesh>(null)
  const screens = useRef<InstancedMesh>(null)
  const bodies = useRef<InstancedMesh>(null)
  const heads = useRef<InstancedMesh>(null)
  const chairs = useRef<InstancedMesh>(null)
  const controls = useRef<OrbitControlsImpl>(null)
  const scratch = useMemo(() => new THREE.Object3D(), [])
  const screenBase = useMemo(() => SEATS.map((seat) => new THREE.Color(seat.screen)), [])

  const copy = bot.departments?.length === FLOOR_DESKS.length ? bot.departments : FLOOR_DESKS

  useLayoutEffect(() => {
    const place = (mesh: InstancedMesh | null, y: number, zOff: number) => {
      if (!mesh) return
      SEATS.forEach((seat, i) => {
        scratch.position.set(seat.x, y, seat.z + zOff)
        scratch.rotation.set(0, 0, 0)
        scratch.scale.set(1, 1, 1)
        scratch.updateMatrix()
        mesh.setMatrixAt(i, scratch.matrix)
      })
      mesh.count = SEATS.length
      mesh.instanceMatrix.needsUpdate = true
    }
    place(desks.current, 0.38, -0.34)
    place(screens.current, 0.78, -0.48)
    place(bodies.current, 0.92, 0.08)
    place(heads.current, 1.28, 0.08)
    place(chairs.current, 1.02, 0.28)
    if (desks.current) paint(desks.current, (seat) => FLOOR_DESKS[seat.desk].color)
    if (screens.current) paint(screens.current, (seat) => seat.screen)
    if (bodies.current) paint(bodies.current, (seat) => seat.suit)
    if (heads.current) paint(heads.current, (_, i) => (i % 11 === 0 ? '#d7b899' : '#e4c4a4'))
    if (chairs.current) paint(chairs.current, (seat) => seat.suit)
  }, [scratch])

  useFrame(({ clock }) => {
    const mesh = heads.current
    const t = clock.getElapsedTime()
    if (mesh) {
      for (let i = 0; i < SEATS.length; i += 6) {
        const seat = SEATS[i]
        const bob = Math.sin(t * 1.6 + i) * 0.015
        scratch.position.set(seat.x, 1.28 + bob, seat.z + 0.08)
        scratch.rotation.set(0, 0, 0)
        scratch.updateMatrix()
        mesh.setMatrixAt(i, scratch.matrix)
      }
      mesh.instanceMatrix.needsUpdate = true
    }
    const screensMesh = screens.current
    if (screensMesh) {
      for (let i = 0; i < SEATS.length; i += 5) {
        const pulse = 0.55 + Math.sin(t * 2.2 + i) * 0.45
        screensMesh.setColorAt(i, screenBase[i].clone().multiplyScalar(pulse))
      }
      if (screensMesh.instanceColor) screensMesh.instanceColor.needsUpdate = true
    }
  })

  const line = `${head} traders on six desks. One book. It does not trade.`

  return (
    <>
      <color attach="background" args={['#12082a']} />
      <fog attach="fog" args={['#14082e', 18, 42]} />
      <PerspectiveCamera makeDefault fov={46} near={0.08} far={80} position={[0.2, 5.6, 4.6]} />
      <OrbitControls
        ref={controls}
        makeDefault
        target={[0, 0.9, -0.6]}
        enableDamping
        dampingFactor={0.08}
        enablePan={false}
        minDistance={3.2}
        maxDistance={14}
        minPolarAngle={0.35}
        maxPolarAngle={1.25}
      />
      <ambientLight intensity={0.55} color="#d8c8ff" />
      <directionalLight position={[4, 10, 6]} intensity={0.55} color="#fff4d2" />
      <pointLight position={[0, 4.2, 0]} intensity={0.7} color="#f5d76e" distance={16} />
      <pointLight position={[-4, 3, -2]} intensity={0.28} color="#3ddcff" distance={12} />
      <pointLight position={[4, 3, 2]} intensity={0.28} color="#ff4d6a" distance={12} />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[16, 14]} />
        <meshStandardMaterial color="#14110e" roughness={0.9} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0]}>
        <planeGeometry args={[1.35, 12.2]} />
        <meshStandardMaterial color="#2a2418" emissive="#c6a15b" emissiveIntensity={0.16} />
      </mesh>

      {FLOOR_DESKS.map((desk, i) => {
        const z = bandZ(i)
        return (
          <group key={desk.id}>
            {[-3.05, 3.05].map((x) => (
              <mesh key={x} rotation={[-Math.PI / 2, 0, 0]} position={[x, 0.018, z]}>
                <planeGeometry args={[4.35, 1.55]} />
                <meshStandardMaterial color="#1a140f" emissive={desk.color} emissiveIntensity={0.18} />
              </mesh>
            ))}
            <mesh position={[2.45, 3.22, z]}>
              <sphereGeometry args={[0.07, 10, 10]} />
              <meshStandardMaterial color={desk.color} emissive={desk.color} emissiveIntensity={1.4} toneMapped={false} />
            </mesh>
            <Html position={[-6.55, 2.45, z]} center distanceFactor={11} zIndexRange={[20, 0]} style={{ pointerEvents: 'none' }}>
              <div className="wall-street-flag" style={{ borderColor: desk.color, color: desk.color }}>
                {desk.name}
                <span>{desk.seats}</span>
              </div>
            </Html>
          </group>
        )
      })}

      <mesh position={[0, 0.55, -0.15]}>
        <boxGeometry args={[0.62, 1.1, 0.4]} />
        <meshStandardMaterial color="#2a2116" metalness={0.35} roughness={0.45} />
      </mesh>
      <mesh position={[0, 1.7, -0.15]}>
        <boxGeometry args={[1.55, 1.28, 0.05]} />
        <meshStandardMaterial color="#1a140c" emissive="#c6a15b" emissiveIntensity={0.2} />
      </mesh>
      <Html position={[0, 1.7, -0.08]} center distanceFactor={10} zIndexRange={[30, 0]} style={{ pointerEvents: 'none' }}>
        <div className="wall-street-board">
          <strong>ONE BOOK</strong>
          <em>cash $0 · {head} staff · does not trade</em>
          <ul>
            {copy.map((desk) => (
              <li key={desk.id}>
                <b>{desk.name}</b>
                <span>{desk.job}</span>
              </li>
            ))}
          </ul>
        </div>
      </Html>

      <mesh position={[0, 2.1, -6.4]}>
        <boxGeometry args={[16, 4.2, 0.16]} />
        <meshStandardMaterial color="#100c18" />
      </mesh>
      <mesh position={[0, 2.1, 6.4]}>
        <boxGeometry args={[16, 4.2, 0.16]} />
        <meshStandardMaterial color="#160e2c" />
      </mesh>
      <mesh position={[-7.9, 2.1, 0]}>
        <boxGeometry args={[0.16, 4.2, 14]} />
        <meshStandardMaterial color="#100c18" />
      </mesh>
      <mesh position={[7.9, 2.1, 0]}>
        <boxGeometry args={[0.16, 4.2, 14]} />
        <meshStandardMaterial color="#100c18" />
      </mesh>
      <Html position={[0, 3.15, -6.2]} center distanceFactor={12} zIndexRange={[20, 0]} style={{ pointerEvents: 'none' }}>
        <div className="wall-street-sign">
          <strong>WALL STREET</strong>
          <span>{line}</span>
        </div>
      </Html>

      <instancedMesh ref={desks} args={[undefined, undefined, SEATS.length]}>
        <boxGeometry args={[0.62, 0.06, 0.42]} />
        <meshStandardMaterial roughness={0.45} metalness={0.2} emissive="#ffffff" emissiveIntensity={0.08} />
      </instancedMesh>
      <instancedMesh ref={screens} args={[undefined, undefined, SEATS.length]}>
        <boxGeometry args={[0.34, 0.22, 0.03]} />
        <meshStandardMaterial emissive="#ffffff" emissiveIntensity={0.4} toneMapped={false} />
      </instancedMesh>
      <instancedMesh ref={bodies} args={[undefined, undefined, SEATS.length]}>
        <boxGeometry args={[0.28, 0.42, 0.16]} />
        <meshStandardMaterial roughness={0.7} />
      </instancedMesh>
      <instancedMesh ref={heads} args={[undefined, undefined, SEATS.length]}>
        <sphereGeometry args={[0.1, 8, 8]} />
        <meshStandardMaterial roughness={0.55} />
      </instancedMesh>
      <instancedMesh ref={chairs} args={[undefined, undefined, SEATS.length]}>
        <boxGeometry args={[0.3, 0.28, 0.05]} />
        <meshStandardMaterial roughness={0.65} />
      </instancedMesh>

      <NeonBloom strength={0.4} lite />
    </>
  )
}
