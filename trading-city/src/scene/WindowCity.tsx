import { useMemo, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import { BEAM_COLORS } from '../data/format'
import { GridFloor } from './GridFloor'
import { Skyline, Starfield } from './Skyline'
import { Vault } from './Vault'

const GLASS_ASPECT = 1536 / 512

type Block = {
  x: number
  z: number
  width: number
  depth: number
  height: number
  seed: number
}

/** Across-the-street offices. A gap down the middle leaves the vault in view. */
const BLOCKS: Block[] = [
  { x: -3.45, z: 1.25, width: 2.65, depth: 2.3, height: 9.2, seed: 4 },
  { x: 3.55, z: 0.72, width: 2.75, depth: 2.45, height: 8.4, seed: 9 },
  { x: -2.55, z: -3.35, width: 2.05, depth: 2.05, height: 10.4, seed: 15 },
  { x: 2.7, z: -4.15, width: 1.95, depth: 2.0, height: 9.6, seed: 22 },
]

/**
 * Eye-level camera just outside the glass, looking straight down the street.
 * The pane is a wide short band, so the shot stays level instead of overhead.
 */
function StreetCamera() {
  const cam = useRef<Cam>(null)
  useFrame(() => {
    // Slightly up, the way a desk looks out at the floors across the street.
    // The office monitors cover the lower glass, so the facades sit in the upper band.
    cam.current?.lookAt(0, 3.35, -1.2)
  })
  return (
    <PerspectiveCamera
      ref={cam}
      makeDefault
      fov={32}
      aspect={GLASS_ASPECT}
      near={0.1}
      far={160}
      position={[0.08, 1.35, 8.5]}
    />
  )
}

function FacadeWindows({
  width,
  depth,
  seed,
  color,
  minY,
  maxY,
}: {
  width: number
  depth: number
  seed: number
  color: string
  minY: number
  maxY: number
}) {
  const lights = useMemo(() => {
    const out: { key: string; position: [number, number, number]; warm: boolean }[] = []
    const z = depth / 2 + 0.03
    for (let y = minY; y < maxY - 0.2; y += 0.46) {
      for (let col = -2; col <= 2; col++) {
        if (((y * 13 + col * 5 + seed * 7) | 0) % 5 === 0) continue
        out.push({
          key: `${y}-${col}`,
          position: [col * (width * 0.16), y, z],
          warm: ((col + seed) & 1) === 0,
        })
      }
    }
    return out
  }, [depth, maxY, minY, seed, width])

  return (
    <>
      {lights.map((w) => (
        <mesh key={w.key} position={w.position}>
          <boxGeometry args={[0.16, 0.18, 0.04]} />
          <meshBasicMaterial color={w.warm ? '#f4f0d4' : color} toneMapped={false} />
        </mesh>
      ))}
    </>
  )
}

function StreetBlock({ index, block }: { index: number; block: Block }) {
  const color = BEAM_COLORS[index % BEAM_COLORS.length]
  const { x, z, width, depth, height, seed } = block

  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, height / 2, 0]}>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color="#07060f" roughness={0.9} metalness={0.08} />
      </mesh>
      <FacadeWindows width={width} depth={depth} seed={seed} color={color} minY={0.45} maxY={height} />
      <mesh position={[0, height + 0.06, 0]}>
        <boxGeometry args={[width + 0.18, 0.08, depth + 0.18]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <mesh position={[0, height + 2.4, 0]}>
        <cylinderGeometry args={[0.1, 0.18, 4.6, 14]} />
        <meshBasicMaterial color={color} transparent opacity={0.85} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0, height + 1.1, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.42, 0.035, 8, 24]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
    </group>
  )
}

/**
 * What the office glass shows: a level look out across the street at the other
 * towers, with the vault down the block. No figures in those buildings.
 */
export function CityGlass() {
  return (
    <>
      <color attach="background" args={['#0c0424']} />
      <fog attach="fog" args={['#1a0740', 18, 58]} />
      <StreetCamera />
      <ambientLight intensity={0.38} color="#c9d4ea" />
      <directionalLight position={[4, 10, 6]} intensity={0.42} color="#d5e4ff" />
      <Starfield count={420} />
      <GridFloor plaza={false} size={70} />
      <Skyline z={-26} width={64} />
      <Skyline z={-34} width={78} />
      <Vault lights={false} position={[0, 0, -15.5]} />
      {BLOCKS.map((block, i) => (
        <StreetBlock key={`${block.x}-${block.z}`} index={i} block={block} />
      ))}
    </>
  )
}
