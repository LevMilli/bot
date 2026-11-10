import { useLayoutEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Group, InstancedMesh, Mesh } from 'three'
import type { BotRow } from '../types'
import { beamColorFor, towerClosed } from '../data/format'
import { isSupportTower } from '../data/floorMap'
import { TowerHologram } from '../hud/Holograms'

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
  sparse = false,
}: {
  height: number
  width: number
  seed: number
  offline: boolean
  /** Filler towers: fewer rows/faces so the plaza stays interactive. */
  sparse?: boolean
}) {
  const mesh = useRef<InstancedMesh>(null)
  const yStep = sparse ? 0.75 : 0.52
  const colMin = sparse ? -1 : -2
  const colMax = sparse ? 1 : 2
  // All four façades — front/back (+z/−z) and sides (+x/−x).
  const facesPer = 4

  const count = useMemo(() => {
    let n = 0
    for (let y = 0.35; y < height - 0.25; y += yStep) {
      for (let col = colMin; col <= colMax; col++) {
        if (((y * 17 + col * 5 + seed * 11) | 0) % 7 === 0) continue
        n += facesPer
      }
    }
    return Math.max(n, 1)
  }, [height, seed, yStep, colMin, colMax, facesPer])

  useLayoutEffect(() => {
    if (!mesh.current) return
    const dummy = new THREE.Object3D()
    let i = 0
    const half = width / 2 + 0.015
    for (let y = 0.35; y < height - 0.25; y += yStep) {
      for (let col = colMin; col <= colMax; col++) {
        if (((y * 17 + col * 5 + seed * 11) | 0) % 7 === 0) continue
        const o = col * 0.22
        // Front / back
        dummy.rotation.set(0, 0, 0)
        dummy.position.set(o, y, half)
        dummy.updateMatrix()
        mesh.current!.setMatrixAt(i++, dummy.matrix)
        dummy.position.set(o, y, -half)
        dummy.updateMatrix()
        mesh.current!.setMatrixAt(i++, dummy.matrix)
        // Left / right — rotate so the pane sits on the side wall
        dummy.rotation.set(0, Math.PI / 2, 0)
        dummy.position.set(half, y, o)
        dummy.updateMatrix()
        mesh.current!.setMatrixAt(i++, dummy.matrix)
        dummy.position.set(-half, y, o)
        dummy.updateMatrix()
        mesh.current!.setMatrixAt(i++, dummy.matrix)
      }
    }
    mesh.current.count = i
    mesh.current.instanceMatrix.needsUpdate = true
  }, [count, height, seed, width, yStep, colMin, colMax])

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, count]}>
      <boxGeometry args={[0.08, 0.1, 0.04]} />
      <meshBasicMaterial color={offline ? '#2a3348' : '#f4f0d4'} />
    </instancedMesh>
  )
}

function TradeTower({ bot, index, position, selected, onSelect, vista = false }: Props) {
  const beamGroup = useRef<Group>(null)
  const beamCore = useRef<Mesh>(null)
  const color = beamColorFor(bot.id, index)
  const offline = bot.present === false
  const closed = towerClosed(bot)
  const street = bot.id === 'wall-street'
  const height = street ? 10.8 : offline ? 5.4 : 7.6 + (index % 3) * 1.35 + (index === 0 ? 1.2 : 0)
  const width = street ? 2.25 : 1.9 + (index % 2) * 0.28
  const hero = index === 0 && !offline

  useFrame(({ clock }) => {
    if (closed) return
    const t = clock.getElapsedTime()
    const pulse = 0.7 + Math.sin(t * 2.4 + index) * 0.28
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
        <meshStandardMaterial
          color="#050510"
          emissive={closed ? '#000000' : color}
          emissiveIntensity={closed ? 0 : 0.18}
        />
      </mesh>
      {!closed && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[(width + 0.35) / 2, (width + 0.55) / 2, 4]} />
          <meshBasicMaterial color={color} transparent opacity={0.75} />
        </mesh>
      )}

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

      <WindowInstances height={height} width={width} seed={index + 3} offline={closed} sparse />

      {/* roof cap */}
      <mesh position={[0, height + 0.08, 0]}>
        <boxGeometry args={[width + 0.22, 0.16, width + 0.22]} />
        <meshStandardMaterial
          color="#0c0c14"
          emissive={closed ? '#000000' : color}
          emissiveIntensity={closed ? 0 : 0.7}
        />
      </mesh>
      {street && !closed && (
        <mesh position={[0, height + 0.32, 0]}>
          <boxGeometry args={[width + 0.46, 0.18, width + 0.46]} />
          <meshStandardMaterial color="#1a1408" emissive="#c6a15b" emissiveIntensity={1.15} />
        </mesh>
      )}

      {/* neon beam + halo rings — dark when the tower is closed */}
      {!closed && (
      <group ref={beamGroup} position={[0, height + 0.2, 0]}>
        <mesh ref={beamCore} position={[0, hero ? 6.4 : 5.6, 0]}>
          <cylinderGeometry args={[hero ? 0.42 : 0.32, hero ? 0.62 : 0.52, hero ? 12.5 : 11, 24]} />
          <meshBasicMaterial color={color} transparent opacity={1} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh position={[0, hero ? 6.4 : 5.6, 0]}>
          <cylinderGeometry args={[hero ? 0.09 : 0.06, hero ? 0.12 : 0.09, hero ? 12.8 : 11.2, 12]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={1} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh position={[0, hero ? 6.4 : 5.6, 0]}>
          <cylinderGeometry args={[hero ? 0.62 : 0.48, hero ? 0.92 : 0.78, hero ? 12.2 : 10.6, 24]} />
          <meshBasicMaterial color={color} transparent opacity={0.35} depthWrite={false} toneMapped={false} />
        </mesh>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <mesh key={i} rotation={[Math.PI / 2, 0, 0]} position={[0, 1.1 + i * 1.4, 0]}>
            <torusGeometry args={[0.62 + i * 0.06 + (hero ? 0.14 : 0), 0.05, 8, 40]} />
            <meshBasicMaterial
              color={i % 2 === 0 ? '#ffffff' : color}
              transparent
              opacity={0.95}
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
      )}

      {!vista && (
        <TowerHologram bot={bot} index={index} height={height} onSelect={onSelect} />
      )}
    </group>
  )
}

/**
 * Support sleeves stay in the plaza palette — black mass, their own neon —
 * but the silhouette is a short relay drum and dish, not a square beam tower.
 */
function SupportRelay({ bot, index, position, selected, onSelect, vista = false }: Props) {
  const halo = useRef<Mesh>(null)
  const dish = useRef<Group>(null)
  const color = beamColorFor(bot.id, index)
  const offline = bot.present === false
  const closed = towerClosed(bot)
  const height = offline ? 3.15 : 4.5
  const radius = 1.05
  const bands = [0.32, 0.58, 0.84]

  useFrame(({ clock }) => {
    if (closed) return
    const t = clock.getElapsedTime()
    if (dish.current) dish.current.rotation.y = t * 0.28 + index
    if (halo.current) {
      halo.current.rotation.z = t * 0.45 + index
      const mat = halo.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = offline ? 0.12 : 0.55 + Math.sin(t * 1.7 + index) * 0.28
    }
  })

  const pick = vista
    ? {}
    : {
        onClick: (e: { stopPropagation: () => void }) => {
          e.stopPropagation()
          onSelect(bot.id)
        },
        onPointerOver: () => {
          document.body.style.cursor = 'pointer'
        },
        onPointerOut: () => {
          document.body.style.cursor = 'default'
        },
      }

  return (
    <group position={position}>
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[radius + 0.62, 8]} />
        <meshStandardMaterial
          color="#050510"
          emissive={closed ? '#000000' : color}
          emissiveIntensity={closed ? 0 : 0.16}
        />
      </mesh>
      {!closed && (
        <mesh position={[0, 0.055, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[radius + 0.28, radius + 0.5, 8]} />
          <meshBasicMaterial color={color} transparent opacity={0.7} toneMapped={false} />
        </mesh>
      )}

      <mesh position={[0, height / 2, 0]} castShadow {...pick}>
        <cylinderGeometry args={[radius, radius * 1.06, height, 8]} />
        <meshStandardMaterial
          color={offline ? '#06050c' : '#07060f'}
          emissive={selected ? color : '#080814'}
          emissiveIntensity={selected ? 0.34 : offline ? 0.03 : 0.07}
          roughness={0.72}
          metalness={0.28}
        />
      </mesh>

      {bands.map((t) => (
        <mesh key={t} position={[0, height * t, 0]}>
          <cylinderGeometry args={[radius + 0.045, radius + 0.045, 0.07, 8]} />
          <meshBasicMaterial
            color={closed ? '#2a3348' : color}
            transparent
            opacity={closed ? 0.2 : 0.92}
            toneMapped={false}
          />
        </mesh>
      ))}

      <mesh position={[0, height + 0.08, 0]}>
        <cylinderGeometry args={[radius * 0.42, radius * 0.72, 0.18, 8]} />
        <meshStandardMaterial
          color="#0c0c14"
          emissive={closed ? '#000000' : color}
          emissiveIntensity={closed ? 0 : 0.65}
        />
      </mesh>

      <group ref={dish} position={[0, height + 0.72, 0]}>
        <mesh rotation={[Math.PI, 0, 0]} position={[0, 0.16, 0]}>
          <coneGeometry args={[0.78, 0.28, 8, 1, true]} />
          <meshStandardMaterial
            color="#101018"
            emissive={closed ? '#000000' : color}
            emissiveIntensity={closed ? 0 : 0.55}
            metalness={0.45}
            roughness={0.32}
            side={THREE.DoubleSide}
          />
        </mesh>
        <mesh position={[0, 0.02, 0]}>
          <cylinderGeometry args={[0.045, 0.045, 0.55, 8]} />
          <meshBasicMaterial color={closed ? '#2a3348' : '#f4f7ff'} toneMapped={false} />
        </mesh>
      </group>

      {!closed && (
        <mesh ref={halo} position={[0, height + 1.28, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.92, 0.03, 8, 28]} />
          <meshBasicMaterial color={color} transparent opacity={0.8} depthWrite={false} toneMapped={false} />
        </mesh>
      )}

      {!vista && <TowerHologram bot={bot} index={index} height={height + 1.15} onSelect={onSelect} />}
    </group>
  )
}

export function Tower(props: Props) {
  if (isSupportTower(props.bot.id)) return <SupportRelay {...props} />
  return <TradeTower {...props} />
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
      <WindowInstances height={height} width={width} seed={seed} offline={false} sparse />
    </group>
  )
}
