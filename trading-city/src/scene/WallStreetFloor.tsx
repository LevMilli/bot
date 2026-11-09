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

type Seat = { x: number; z: number; suit: string; screen: string }

const SUITS = ['#1b2a4a', '#243044', '#2a241c', '#1a1c24', '#3a2c24', '#15283a']
const SCREENS = ['#39ff14', '#39ff14', '#7CFF6B', '#ff4d6a', '#f4f0d4', '#39ff14']

function buildSeats(): Seat[] {
  const seats: Seat[] = []
  const rows = 12
  const perSide = 5
  const xGap = 0.78
  const zGap = 0.84
  const aisle = 1.45
  let i = 0
  for (let r = 0; r < rows; r++) {
    const z = (r - (rows - 1) / 2) * zGap
    for (let side = 0; side < 2; side++) {
      for (let c = 0; c < perSide; c++) {
        const x = (side === 0 ? -1 : 1) * (aisle + c * xGap)
        seats.push({
          x,
          z,
          suit: SUITS[i % SUITS.length],
          screen: SCREENS[i % SCREENS.length],
        })
        i += 1
      }
    }
  }
  return seats
}

const SEATS = buildSeats()

function paint(mesh: InstancedMesh, colorOf: (seat: Seat, index: number) => string) {
  for (let i = 0; i < SEATS.length; i++) {
    mesh.setColorAt(i, new THREE.Color(colorOf(SEATS[i], i)))
  }
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
}

/**
 * The Wall Street tower interior: one pit, 120 traders, one book.
 * Traders are instanced staff. They do not place trades.
 */
export function WallStreetScene({ bot }: { bot: BotRow }) {
  const head = bot.traders && bot.traders >= 100 ? bot.traders : WALL_STREET_HEADCOUNT
  const desks = useRef<InstancedMesh>(null)
  const screens = useRef<InstancedMesh>(null)
  const bodies = useRef<InstancedMesh>(null)
  const heads = useRef<InstancedMesh>(null)
  const controls = useRef<OrbitControlsImpl>(null)
  const scratch = useMemo(() => new THREE.Object3D(), [])

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
    if (desks.current) paint(desks.current, () => '#3a2a1c')
    if (screens.current) paint(screens.current, (seat) => seat.screen)
    if (bodies.current) paint(bodies.current, (seat) => seat.suit)
    if (heads.current) paint(heads.current, (_, i) => (i % 11 === 0 ? '#d7b899' : '#e4c4a4'))
  }, [scratch])

  useFrame(({ clock }) => {
    const mesh = heads.current
    if (!mesh) return
    const t = clock.getElapsedTime()
    for (let i = 0; i < SEATS.length; i += 6) {
      const seat = SEATS[i]
      const bob = Math.sin(t * 1.6 + i) * 0.015
      scratch.position.set(seat.x, 1.28 + bob, seat.z + 0.08)
      scratch.rotation.set(0, 0, 0)
      scratch.updateMatrix()
      mesh.setMatrixAt(i, scratch.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true
  })

  const line = `${head} traders on the floor. One book. It does not trade.`

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
      <pointLight position={[-4, 3, -2]} intensity={0.35} color="#39ff14" distance={10} />
      <pointLight position={[4, 3, -2]} intensity={0.35} color="#ff4d6a" distance={10} />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
        <planeGeometry args={[16, 14]} />
        <meshStandardMaterial color="#14110e" roughness={0.9} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0]}>
        <planeGeometry args={[1.35, 12.2]} />
        <meshStandardMaterial color="#2a2418" emissive="#c6a15b" emissiveIntensity={0.12} />
      </mesh>

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
        <meshStandardMaterial roughness={0.6} />
      </instancedMesh>
      <instancedMesh ref={screens} args={[undefined, undefined, SEATS.length]}>
        <boxGeometry args={[0.28, 0.2, 0.03]} />
        <meshStandardMaterial emissive="#ffffff" emissiveIntensity={0.45} toneMapped={false} />
      </instancedMesh>
      <instancedMesh ref={bodies} args={[undefined, undefined, SEATS.length]}>
        <boxGeometry args={[0.28, 0.42, 0.16]} />
        <meshStandardMaterial roughness={0.7} />
      </instancedMesh>
      <instancedMesh ref={heads} args={[undefined, undefined, SEATS.length]}>
        <sphereGeometry args={[0.1, 8, 8]} />
        <meshStandardMaterial roughness={0.55} />
      </instancedMesh>

      <NeonBloom strength={0.35} lite />
    </>
  )
}
