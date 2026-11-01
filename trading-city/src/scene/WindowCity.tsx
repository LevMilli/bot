import { useMemo, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow } from '../types'
import { BEAM_COLORS } from '../data/format'
import { BotFigure } from './BotFigure'
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
    // The office monitors cover the lower glass, so the crew sits in the upper band.
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

function WorkBay({ bot, index, block }: { bot: BotRow; index: number; block: Block }) {
  const color = bot.paused ? '#5c6b7a' : BEAM_COLORS[index % BEAM_COLORS.length]
  const { x, z, width, depth, height, seed } = block
  const deck = 2.05
  const lobbyH = 2.25
  const lobbyTop = deck + lobbyH
  const botZ = depth / 2 - 0.7
  const face = x < 0 ? -1.08 : 1.08

  return (
    <group position={[x, 0, z]}>
      {/* Street podium, open working floor, tower above. */}
      <mesh position={[0, deck / 2, 0]}>
        <boxGeometry args={[width, deck, depth]} />
        <meshStandardMaterial color="#090814" roughness={0.9} metalness={0.08} />
      </mesh>
      <mesh position={[0, lobbyTop + Math.max(height - lobbyTop, 0.4) / 2, 0]}>
        <boxGeometry args={[width, Math.max(height - lobbyTop, 0.4), depth]} />
        <meshStandardMaterial color="#07060f" roughness={0.9} metalness={0.08} />
      </mesh>
      <mesh position={[0, deck + lobbyH / 2, -depth / 2 + 0.08]}>
        <boxGeometry args={[width, lobbyH, 0.12]} />
        <meshStandardMaterial color="#100e1a" roughness={0.88} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[side * (width / 2 - 0.07), deck + lobbyH / 2, 0]}>
          <boxGeometry args={[0.12, lobbyH, depth]} />
          <meshStandardMaterial color="#0c0b16" roughness={0.88} />
        </mesh>
      ))}
      <mesh position={[0, deck, 0]}>
        <boxGeometry args={[width - 0.06, 0.08, depth - 0.06]} />
        <meshStandardMaterial color="#1a1724" roughness={0.62} metalness={0.2} />
      </mesh>
      <mesh position={[0, lobbyTop, 0]}>
        <boxGeometry args={[width, 0.08, depth]} />
        <meshStandardMaterial color="#0c0b16" roughness={0.86} />
      </mesh>

      {([-1, 1] as const).map((side) => (
        <mesh key={`jamb-${side}`} position={[side * (width * 0.4), deck + lobbyH / 2, depth / 2 + 0.03]}>
          <boxGeometry args={[0.06, lobbyH, 0.06]} />
          <meshStandardMaterial color="#8b95a8" metalness={0.65} roughness={0.28} />
        </mesh>
      ))}
      <mesh position={[0, deck + 0.04, depth / 2 + 0.03]}>
        <boxGeometry args={[width * 0.82, 0.06, 0.06]} />
        <meshStandardMaterial color="#8b95a8" metalness={0.65} roughness={0.28} />
      </mesh>
      <mesh position={[0, lobbyTop - 0.04, depth / 2 + 0.03]}>
        <boxGeometry args={[width * 0.82, 0.06, 0.06]} />
        <meshStandardMaterial color="#8b95a8" metalness={0.65} roughness={0.28} />
      </mesh>

      <mesh position={[0, deck + lobbyH / 2, depth / 2 + 0.05]} renderOrder={2}>
        <planeGeometry args={[width * 0.74, lobbyH - 0.16]} />
        <meshBasicMaterial color="#9af4ff" transparent opacity={0.1} depthWrite={false} toneMapped={false} />
      </mesh>

      <mesh position={[0, height + 0.06, 0]}>
        <boxGeometry args={[width + 0.18, 0.08, depth + 0.18]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>

      <FacadeWindows width={width} depth={depth} seed={seed} color={color} minY={0.4} maxY={deck - 0.15} />
      <FacadeWindows width={width} depth={depth} seed={seed + 3} color={color} minY={lobbyTop + 0.35} maxY={height} />

      <mesh position={[0, height + 2.4, 0]}>
        <cylinderGeometry args={[0.1, 0.18, 4.6, 14]} />
        <meshBasicMaterial color={color} transparent opacity={0.85} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0, height + 1.1, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.42, 0.035, 8, 24]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>

      <group position={[x < 0 ? -0.18 : 0.18, deck, botZ]} rotation={[0, face, 0]}>
        <mesh position={[0, 0.7, -0.62]}>
          <boxGeometry args={[0.86, 0.06, 0.52]} />
          <meshStandardMaterial color="#141820" metalness={0.35} roughness={0.45} />
        </mesh>
        <mesh position={[0, 0.95, -0.86]}>
          <boxGeometry args={[0.7, 0.46, 0.05]} />
          <meshBasicMaterial color={color} toneMapped={false} />
        </mesh>
        <mesh position={[0, 0.74, -0.72]}>
          <boxGeometry args={[0.36, 0.02, 0.18]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
        <pointLight position={[0, 1.55, -0.35]} intensity={1.35} color={color} distance={3.6} />
        <BotFigure pose="work" seated={false} />
      </group>
    </group>
  )
}

/**
 * What the office glass shows: a level look out across the street at the other
 * towers, with the rest of the roster working inside the near floors, and the
 * vault down the block.
 */
export function CityGlass({ bots, exceptId }: { bots: BotRow[]; exceptId?: string }) {
  const crew = useMemo(() => {
    const others = bots.filter((b) => b.id !== exceptId)
    const onShift = others.filter((b) => b.present !== false)
    return (onShift.length ? onShift : others).slice(0, BLOCKS.length)
  }, [bots, exceptId])

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
      {crew.map((bot, i) => (
        <WorkBay key={bot.id} bot={bot} index={i} block={BLOCKS[i]} />
      ))}
    </>
  )
}
