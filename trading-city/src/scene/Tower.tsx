import { useLayoutEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Group, InstancedMesh, Mesh } from 'three'
import type { BotRow } from '../types'
import { BEAM_COLORS } from '../data/format'

type Props = {
  bot: BotRow
  index: number
  position: [number, number, number]
  selected: boolean
  onSelect: (id: string) => void
  /** Window vista: same towers, no plaza lights (those don't scale and flood the room). */
  vista?: boolean
}

function WindowInstances({
  height,
  width,
  seed,
  offline,
}: {
  height: number
  width: number
  seed: number
  offline: boolean
}) {
  const mesh = useRef<InstancedMesh>(null)
  const count = useMemo(() => {
    let n = 0
    for (let y = 0.35; y < height - 0.25; y += 0.28) {
      for (let col = -3; col <= 3; col++) {
        if (((y * 17 + col * 5 + seed * 11) | 0) % 7 === 0) continue
        n += 4
      }
    }
    return n
  }, [height, seed])

  useLayoutEffect(() => {
    if (!mesh.current) return
    const dummy = new THREE.Object3D()
    let i = 0
    for (let y = 0.35; y < height - 0.25; y += 0.28) {
      for (let col = -3; col <= 3; col++) {
        if (((y * 17 + col * 5 + seed * 11) | 0) % 7 === 0) continue
        const x = col * 0.22
        const faces: [number, number, number][] = [
          [x, y, width / 2 + 0.015],
          [x, y, -width / 2 - 0.015],
          [width / 2 + 0.015, y, x],
          [-width / 2 - 0.015, y, x],
        ]
        for (const p of faces) {
          dummy.position.set(p[0], p[1], p[2])
          dummy.updateMatrix()
          mesh.current!.setMatrixAt(i++, dummy.matrix)
        }
      }
    }
    mesh.current.count = i
    mesh.current.instanceMatrix.needsUpdate = true
  }, [count, height, seed, width])

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, count]}>
      <boxGeometry args={[0.08, 0.1, 0.04]} />
      <meshBasicMaterial color={offline ? '#2a3348' : '#f4f0d4'} />
    </instancedMesh>
  )
}

export function Tower({ bot, index, position, selected, onSelect, vista = false }: Props) {
  const beamGroup = useRef<Group>(null)
  const beamCore = useRef<Mesh>(null)
  const color = BEAM_COLORS[index % BEAM_COLORS.length]
  const offline = bot.present === false
  const height = offline ? 5.4 : 7.6 + (index % 3) * 1.35 + (index === 0 ? 1.2 : 0)
  const width = 1.9 + (index % 2) * 0.28
  const hero = index === 0 && !offline

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const pulse = offline ? 0.1 : 0.7 + Math.sin(t * 2.4 + index) * 0.28
    if (beamCore.current) {
      const mat = beamCore.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = pulse
    }
    if (beamGroup.current) {
      beamGroup.current.children.forEach((child, i) => {
        if (i < 3) return
        child.position.y = 1.1 + ((t * 1.35 + i * 1.05 + index) % 6.2)
        const s = 0.72 + Math.sin(t * 3 + i) * 0.14
        child.scale.set(s, 1, s)
      })
    }
  })

  return (
    <group position={position}>
      {/* neon baseplate */}
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[width + 0.55, width + 0.55]} />
        <meshStandardMaterial color="#050510" emissive={color} emissiveIntensity={0.18} />
      </mesh>
      <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[(width + 0.35) / 2, (width + 0.55) / 2, 4]} />
        <meshBasicMaterial color={color} transparent opacity={0.75} />
      </mesh>

      <mesh
        position={[0, height / 2, 0]}
        castShadow
        onClick={
          vista
            ? undefined
            : (e) => {
                e.stopPropagation()
                onSelect(bot.id)
              }
        }
        onPointerOver={
          vista
            ? undefined
            : () => {
                document.body.style.cursor = 'pointer'
              }
        }
        onPointerOut={
          vista
            ? undefined
            : () => {
                document.body.style.cursor = 'default'
              }
        }
      >
        <boxGeometry args={[width, height, width]} />
        <meshStandardMaterial
          color={offline ? '#06050c' : '#05040c'}
          emissive={selected ? color : '#080814'}
          emissiveIntensity={selected ? 0.32 : offline ? 0.03 : 0.06}
          roughness={0.88}
          metalness={0.12}
        />
      </mesh>

      <WindowInstances height={height} width={width} seed={index + 3} offline={offline} />

      {/* roof cap */}
      <mesh position={[0, height + 0.08, 0]}>
        <boxGeometry args={[width + 0.22, 0.16, width + 0.22]} />
        <meshStandardMaterial color="#0c0c14" emissive={color} emissiveIntensity={0.7} />
      </mesh>

      {/* neon beam + halo rings */}
      <group ref={beamGroup} position={[0, height + 0.2, 0]}>
        <mesh ref={beamCore} position={[0, hero ? 6.4 : 5.6, 0]}>
          <cylinderGeometry args={[hero ? 0.42 : 0.32, hero ? 0.62 : 0.52, hero ? 12.5 : 11, 24]} />
          <meshBasicMaterial color={color} transparent opacity={offline ? 0.18 : 1} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh position={[0, hero ? 6.4 : 5.6, 0]}>
          <cylinderGeometry args={[hero ? 0.16 : 0.11, hero ? 0.22 : 0.17, hero ? 12.8 : 11.2, 12]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={offline ? 0.14 : 1} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh position={[0, hero ? 6.4 : 5.6, 0]}>
          <cylinderGeometry args={[hero ? 0.62 : 0.48, hero ? 0.92 : 0.78, hero ? 12.2 : 10.6, 24]} />
          <meshBasicMaterial color={color} transparent opacity={offline ? 0.06 : 0.35} depthWrite={false} toneMapped={false} />
        </mesh>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <mesh key={i} rotation={[Math.PI / 2, 0, 0]} position={[0, 1.1 + i * 1.4, 0]}>
            <torusGeometry args={[0.62 + i * 0.06 + (hero ? 0.14 : 0), 0.05, 8, 40]} />
            <meshBasicMaterial
              color={i % 2 === 0 ? '#ffffff' : color}
              transparent
              opacity={offline ? 0.1 : 0.95}
              depthWrite={false}
              toneMapped={false}
            />
          </mesh>
        ))}
        {hero && (
          <mesh position={[0, 12.2, 0]} rotation={[0, 0, 0]}>
            <torusGeometry args={[1.15, 0.04, 8, 48]} />
            <meshBasicMaterial color="#ffffff" />
          </mesh>
        )}
        {hero && (
          <mesh position={[0, 12.2, 0]}>
            <boxGeometry args={[2.6, 0.05, 0.05]} />
            <meshBasicMaterial color="#ffffff" />
          </mesh>
        )}
      </group>

      {!vista && (
        <pointLight
          position={[0, height + 2.2, 0]}
          intensity={offline ? 0.15 : hero ? 2.4 : 1.8}
          color={color}
          distance={12}
        />
      )}

    </group>
  )
}

/** Dense filler skyscraper without hologram / click — packs the plaza like the refs. */
export function FillerTower({
  position,
  height,
  width,
  seed,
}: {
  position: [number, number, number]
  height: number
  width: number
  seed: number
}) {
  return (
    <group position={position}>
      <mesh position={[0, height / 2, 0]}>
        <boxGeometry args={[width, height, width]} />
        <meshStandardMaterial color="#04030a" roughness={0.9} metalness={0.08} />
      </mesh>
      <WindowInstances height={height} width={width} seed={seed} offline={false} />
    </group>
  )
}
