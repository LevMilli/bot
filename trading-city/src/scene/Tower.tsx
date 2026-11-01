import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, Mesh } from 'three'
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
  const beamGroup = useRef<Group>(null)
  const beamCore = useRef<Mesh>(null)
  const color = BEAM_COLORS[index % BEAM_COLORS.length]
  const offline = bot.present === false
  const height = offline ? 5.2 : 7.2 + (index % 3) * 1.1
  const width = 1.85 + (index % 2) * 0.25

  const windows = useMemo(() => {
    const pts: [number, number, number][] = []
    for (let y = 0.55; y < height - 0.35; y += 0.48) {
      for (let col = -2; col <= 2; col++) {
        if ((y * 10 + col * 3 + index * 7) % 5 === 0) continue
        const x = col * 0.28
        pts.push([x, y, width / 2 + 0.02])
        pts.push([x, y, -width / 2 - 0.02])
        pts.push([width / 2 + 0.02, y, col * 0.28])
        pts.push([-width / 2 - 0.02, y, col * 0.28])
      }
    }
    return pts
  }, [height, index, width])

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const pulse = offline ? 0.12 : 0.65 + Math.sin(t * 2.4 + index) * 0.3
    if (beamCore.current) {
      const mat = beamCore.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = pulse
    }
    if (beamGroup.current) {
      beamGroup.current.children.forEach((child, i) => {
        if (i === 0) return
        child.position.y = 1.2 + ((t * 1.4 + i * 1.1 + index) % 5.5)
        const s = 0.7 + Math.sin(t * 3 + i) * 0.15
        child.scale.set(s, 1, s)
      })
    }
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
        <boxGeometry args={[width, height, width]} />
        <meshStandardMaterial
          color={offline ? '#07060e' : '#08070f'}
          emissive={selected ? color : '#0a0a18'}
          emissiveIntensity={selected ? 0.28 : offline ? 0.04 : 0.08}
          roughness={0.78}
          metalness={0.2}
        />
      </mesh>

      {windows.map((p, i) => (
        <mesh key={i} position={p}>
          <boxGeometry args={[0.1, 0.1, 0.05]} />
          <meshBasicMaterial color={offline ? '#2a3348' : '#f2f0d8'} />
        </mesh>
      ))}

      {/* roof cap */}
      <mesh position={[0, height + 0.08, 0]}>
        <boxGeometry args={[width + 0.2, 0.16, width + 0.2]} />
        <meshStandardMaterial color="#101018" emissive={color} emissiveIntensity={0.55} />
      </mesh>

      {/* neon beam + halo rings */}
      <group ref={beamGroup} position={[0, height + 0.2, 0]}>
        <mesh ref={beamCore} position={[0, 5.4, 0]}>
          <cylinderGeometry args={[0.28, 0.48, 10.5, 22]} />
          <meshBasicMaterial color={color} transparent opacity={offline ? 0.14 : 0.82} depthWrite={false} />
        </mesh>
        <mesh position={[0, 5.4, 0]}>
          <cylinderGeometry args={[0.1, 0.16, 10.7, 12]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={offline ? 0.12 : 0.95} depthWrite={false} />
        </mesh>
        {/* soft outer glow shell */}
        <mesh position={[0, 5.4, 0]}>
          <cylinderGeometry args={[0.42, 0.7, 10.2, 22]} />
          <meshBasicMaterial color={color} transparent opacity={offline ? 0.05 : 0.22} depthWrite={false} />
        </mesh>
        {[0, 1, 2, 3, 4].map((i) => (
          <mesh key={i} rotation={[Math.PI / 2, 0, 0]} position={[0, 1.2 + i * 1.55, 0]}>
            <torusGeometry args={[0.62 + i * 0.06, 0.04, 8, 36]} />
            <meshBasicMaterial color={color} transparent opacity={offline ? 0.1 : 0.75} depthWrite={false} />
          </mesh>
        ))}
      </group>

      <pointLight
        position={[0, height + 2, 0]}
        intensity={offline ? 0.2 : 1.6}
        color={color}
        distance={10}
      />
    </group>
  )
}
