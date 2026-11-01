import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Mesh } from 'three'
import type { BotRow } from '../types'
import { BEAM_COLORS } from '../data/format'

type Props = {
  bot: BotRow
  index: number
  position: [number, number, number]
  selected: boolean
  onSelect: (id: string) => void
}

export function Tower({ bot, index, position, selected, onSelect }: Props) {
  const beam = useRef<Mesh>(null)
  const color = BEAM_COLORS[index % BEAM_COLORS.length]
  const offline = bot.present === false
  const height = offline ? 4.2 : 6 + (index % 3) * 0.7

  const windows = useMemo(() => {
    const pts: [number, number, number][] = []
    for (let y = 0.6; y < height - 0.4; y += 0.55) {
      for (let side = 0; side < 4; side++) {
        const along = ((y * 3 + side * 7 + index) % 5) / 5
        if (along > 0.45) continue
        const x = side % 2 === 0 ? (side === 0 ? 0.82 : -0.82) : (along - 0.2) * 1.4
        const z = side % 2 === 1 ? (side === 1 ? 0.82 : -0.82) : (along - 0.2) * 1.4
        pts.push([x, y, z])
      }
    }
    return pts
  }, [height, index])

  useFrame(({ clock }) => {
    if (!beam.current) return
    const pulse = offline ? 0.08 : 0.55 + Math.sin(clock.getElapsedTime() * 2.2 + index) * 0.25
    const mat = beam.current.material as { opacity?: number; emissiveIntensity?: number }
    if (mat.opacity != null) mat.opacity = pulse
    if (mat.emissiveIntensity != null) mat.emissiveIntensity = pulse
  })

  return (
    <group position={position}>
      <mesh
        position={[0, height / 2, 0]}
        castShadow
        onClick={(e) => {
          e.stopPropagation()
          onSelect(bot.id)
        }}
        onPointerOver={() => {
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          document.body.style.cursor = 'default'
        }}
      >
        <boxGeometry args={[1.6, height, 1.6]} />
        <meshStandardMaterial
          color={offline ? '#0a0614' : '#0b0a18'}
          emissive={selected ? color : '#10102a'}
          emissiveIntensity={selected ? 0.35 : offline ? 0.05 : 0.12}
          roughness={0.7}
          metalness={0.25}
        />
      </mesh>
      {windows.map((p, i) => (
        <mesh key={i} position={p}>
          <boxGeometry args={[0.12, 0.12, 0.12]} />
          <meshBasicMaterial color={offline ? '#334' : '#f4f0c8'} />
        </mesh>
      ))}
      <mesh ref={beam} position={[0, height + 4.5, 0]}>
        <cylinderGeometry args={[0.18, 0.32, 8.5, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={offline ? 0.12 : 1.35}
          transparent
          opacity={offline ? 0.18 : 0.85}
        />
      </mesh>
      <mesh position={[0, height + 4.5, 0]}>
        <cylinderGeometry args={[0.06, 0.1, 8.6, 8]} />
        <meshBasicMaterial color={color} transparent opacity={offline ? 0.2 : 0.95} />
      </mesh>
      <mesh position={[0, height + 0.05, 0]}>
        <boxGeometry args={[1.75, 0.12, 1.75]} />
        <meshStandardMaterial color="#111" emissive={color} emissiveIntensity={0.4} />
      </mesh>
    </group>
  )
}
