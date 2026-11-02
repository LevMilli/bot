import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, Mesh } from 'three'
import type { Desk } from '../types'
import { VaultHologram } from '../hud/Holograms'

const SHELL = '#07060e'
const BRASS = '#c9a227'
const GOLD = '#f9c80e'
const CYAN = '#2de2e6'
const WINDOW = '#f4f0d4'

function VaultDoor({ clickProps = {} }: { clickProps?: Record<string, unknown> }) {
  const dial = useRef<Group>(null)
  const ring = useRef<Mesh>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (dial.current) dial.current.rotation.z = t * 0.22
    if (ring.current) {
      const mat = ring.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = 0.28 + Math.sin(t * 1.6) * 0.1
    }
  })
  const bolts = Array.from({ length: 12 }, (_, i) => {
    const a = (i / 12) * Math.PI * 2
    return [Math.cos(a) * 0.78, Math.sin(a) * 0.78] as const
  })
  return (
    <group position={[0, 1.35, 2.38]}>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -0.06]} {...clickProps}>
        <cylinderGeometry args={[1.12, 1.12, 0.16, 28]} />
        <meshStandardMaterial color="#12101c" metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.96, 0.96, 0.12, 28]} />
        <meshStandardMaterial color="#1c1828" metalness={0.7} roughness={0.28} />
      </mesh>
      {Array.from({ length: 4 }).map((_, i) => (
        <mesh key={i} position={[0, 0, 0.08]} rotation={[0, 0, (i / 4) * Math.PI]}>
          <boxGeometry args={[1.7, 0.045, 0.03]} />
          <meshStandardMaterial color={BRASS} metalness={0.8} roughness={0.25} />
        </mesh>
      ))}
      {bolts.map(([x, y], i) => (
        <mesh key={i} position={[x, y, 0.1]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.045, 0.045, 0.04, 6]} />
          <meshBasicMaterial color="#8a7a40" />
        </mesh>
      ))}
      <group ref={dial} position={[0, 0, 0.16]}>
        <mesh>
          <torusGeometry args={[0.22, 0.028, 8, 24]} />
          <meshBasicMaterial color={GOLD} toneMapped={false} />
        </mesh>
        <mesh position={[0.14, 0, 0.05]}>
          <boxGeometry args={[0.22, 0.045, 0.03]} />
          <meshBasicMaterial color={GOLD} toneMapped={false} />
        </mesh>
        <mesh position={[0, 0, 0.03]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.06, 0.06, 0.04, 10]} />
          <meshBasicMaterial color={GOLD} toneMapped={false} />
        </mesh>
      </group>
      <mesh ref={ring} position={[0, 0, 0.02]}>
        <ringGeometry args={[0.98, 1.1, 28]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.32} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  )
}

/** Plaza strongbox. Same dark shell and neon as the towers, with a round lock facing the approach. */
export function Vault({
  lights = true,
  position = [0, 0, 5.2],
  desk,
  workers = 0,
  showHolo = true,
  onOpen,
}: {
  lights?: boolean
  /** Plaza keeps the vault toward the overview camera. The office window places it down the street. */
  position?: [number, number, number]
  desk?: Desk
  workers?: number
  showHolo?: boolean
  /** Enter the bank lobby when the vault is clicked. */
  onOpen?: () => void
}) {
  const beacon = useRef<Mesh>(null)

  useFrame(({ clock }) => {
    if (!beacon.current) return
    const mat = beacon.current.material as { opacity?: number }
    if (mat.opacity != null) mat.opacity = 0.55 + Math.sin(clock.getElapsedTime() * 1.8) * 0.25
  })

  const clickProps = onOpen
    ? {
        onClick: (e: { stopPropagation: () => void }) => {
          e.stopPropagation()
          onOpen()
        },
        onPointerOver: () => {
          document.body.style.cursor = 'pointer'
        },
        onPointerOut: () => {
          document.body.style.cursor = 'default'
        },
      }
    : {}

  const slots: [number, number, number, number][] = []
  for (let row = 0; row < 2; row++) {
    const y = 1.05 + row * 0.72
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2
      if (Math.abs(Math.atan2(Math.sin(a), Math.cos(a))) < 0.42 && Math.cos(a) > 0) continue
      slots.push([Math.sin(a) * 2.2, y, Math.cos(a) * 2.2, -a])
    }
  }

  return (
    <group position={position}>
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]} {...clickProps}>
        <circleGeometry args={[3.35, 32]} />
        <meshBasicMaterial color="#050510" />
      </mesh>
      <mesh position={[0, 0.035, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[3.15, 3.42, 40]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[2.72, 2.86, 40]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.7} toneMapped={false} />
      </mesh>

      <mesh position={[0, 0.22, 0]} {...clickProps}>
        <cylinderGeometry args={[2.55, 2.7, 0.36, 8]} />
        <meshStandardMaterial color="#0c0c14" metalness={0.35} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.42, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.55, 0.035, 6, 8]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>

      <mesh position={[0, 1.55, 0]} {...clickProps}>
        <cylinderGeometry args={[2.12, 2.12, 2.15, 8]} />
        <meshStandardMaterial color={SHELL} metalness={0.2} roughness={0.78} />
      </mesh>

      {slots.map(([x, y, z, rot], i) => (
        <mesh key={i} position={[x, y, z]} rotation={[0, rot, 0]}>
          <boxGeometry args={[0.22, 0.12, 0.06]} />
          <meshBasicMaterial color={WINDOW} toneMapped={false} />
        </mesh>
      ))}

      <mesh position={[0, 2.68, 0]}>
        <cylinderGeometry args={[2.16, 2.12, 0.16, 8]} />
        <meshStandardMaterial color="#0c0c14" emissive={GOLD} emissiveIntensity={0.45} />
      </mesh>
      {/* Lock read from the overview camera: a wheel on the roof, same idea as the door. */}
      <mesh position={[0, 2.8, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.62, 0.78, 24]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0, 2.82, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.28, 0.36, 20]} />
        <meshBasicMaterial color={CYAN} toneMapped={false} />
      </mesh>
      <mesh position={[0, 2.83, 0]}>
        <boxGeometry args={[1.35, 0.04, 0.07]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0, 2.83, 0]}>
        <boxGeometry args={[0.07, 0.04, 1.35]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>

      <mesh ref={beacon} position={[0, 2.98, 0]}>
        <cylinderGeometry args={[0.07, 0.11, 0.42, 8]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.7} depthWrite={false} toneMapped={false} />
      </mesh>

      <VaultDoor clickProps={clickProps} />

      <mesh position={[0, 0.14, 2.85]} {...clickProps}>
        <boxGeometry args={[1.7, 0.2, 0.7]} />
        <meshStandardMaterial color="#101018" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.26, 2.85]}>
        <boxGeometry args={[1.72, 0.025, 0.06]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>

      {[Math.PI / 4, (3 * Math.PI) / 4, (5 * Math.PI) / 4, (7 * Math.PI) / 4].map((a) => (
        <group key={a} position={[Math.cos(a) * 3.05, 0, Math.sin(a) * 3.05]}>
          <mesh position={[0, 0.38, 0]}>
            <boxGeometry args={[0.1, 0.7, 0.1]} />
            <meshBasicMaterial color="#12121c" />
          </mesh>
          <mesh position={[0, 0.76, 0]}>
            <boxGeometry args={[0.16, 0.08, 0.16]} />
            <meshBasicMaterial color={CYAN} toneMapped={false} />
          </mesh>
        </group>
      ))}

      {lights && <pointLight position={[0, 3.4, 1.2]} intensity={1.15} color="#9ee7ff" distance={14} />}

      {showHolo && <VaultHologram desk={desk} workers={workers} />}
    </group>
  )
}
