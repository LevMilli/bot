import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, Mesh } from 'three'
import type { Desk } from '../types'
import { VaultHologram } from '../hud/Holograms'

function Crystal({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <group position={position} scale={scale}>
      <mesh>
        <coneGeometry args={[0.28, 1.05, 4]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.95} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.08, 0]}>
        <coneGeometry args={[0.14, 0.7, 4]} />
        <meshBasicMaterial color="#7ef9ff" transparent opacity={0.65} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.42, 0]}>
        <cylinderGeometry args={[0.06, 0.06, 0.28, 6]} />
        <meshBasicMaterial color="#0a4a66" />
      </mesh>
    </group>
  )
}

/** Plaza vault dome — warm trust shell with brass portal ring into the bank lobby. */
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
  /** Enter the bank lobby when the vault pad / dome is clicked. */
  onOpen?: () => void
}) {
  const dome = useRef<Mesh>(null)
  const glow = useRef<Mesh>(null)
  const portal = useRef<Group>(null)
  const portalGlow = useRef<Mesh>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const pulse = 0.7 + Math.sin(t * 1.5) * 0.22
    if (dome.current) {
      const mat = dome.current.material as { emissiveIntensity?: number }
      if (mat.emissiveIntensity != null) mat.emissiveIntensity = pulse
    }
    if (glow.current) {
      const s = 1 + Math.sin(t * 1.5) * 0.045
      glow.current.scale.set(s, 1.35 * s, s)
    }
    if (portal.current) portal.current.rotation.y = t * 0.4
    if (portalGlow.current) {
      const mat = portalGlow.current.material as { opacity?: number }
      if (mat.opacity != null) mat.opacity = 0.35 + Math.sin(t * 2.2) * 0.12
    }
  })

  const crystals: [number, number, number][] = []
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2 + 0.2
    const r = 3.05 + (i % 3) * 0.18
    crystals.push([Math.cos(a) * r, 0.42, Math.sin(a) * r])
  }

  const clickProps = onOpen
    ? {
        onClick: (e: { stopPropagation: () => undefined }) => {
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

  return (
    <group position={position}>
      {/* raised pad */}
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]} {...clickProps}>
        <circleGeometry args={[3.35, 32]} />
        <meshBasicMaterial color="#0a1840" />
      </mesh>
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]} {...clickProps}>
        <ringGeometry args={[3.2, 3.45, 32]} />
        <meshBasicMaterial color="#f9c80e" transparent opacity={0.92} />
      </mesh>
      <mesh position={[0, 0.045, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[2.55, 2.7, 32]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.55} />
      </mesh>
      {/* trust seal spokes on the pad */}
      {Array.from({ length: 8 }).map((_, i) => {
        const a = (i / 8) * Math.PI * 2
        return (
          <mesh
            key={`spoke-${i}`}
            position={[Math.cos(a) * 1.6, 0.035, Math.sin(a) * 1.6]}
            rotation={[-Math.PI / 2, 0, -a]}
          >
            <planeGeometry args={[0.08, 1.1]} />
            <meshBasicMaterial color="#b967ff" transparent opacity={0.35} depthWrite={false} />
          </mesh>
        )
      })}

      <mesh ref={dome} position={[0, 0.05, 0]} scale={[1, 1.38, 1]} {...clickProps}>
        <sphereGeometry args={[2.55, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial
          color="#efe6c4"
          emissive="#fff4b8"
          emissiveIntensity={0.95}
          metalness={0.35}
          roughness={0.16}
          transparent
          opacity={0.98}
        />
      </mesh>

      {/* dark vertical ribs */}
      {Array.from({ length: 6 }).map((_, i) => {
        const a = (i / 6) * Math.PI * 2
        return (
          <mesh
            key={i}
            position={[Math.cos(a) * 2.42, 1.35, Math.sin(a) * 2.42]}
            rotation={[0, -a, 0.08]}
          >
            <boxGeometry args={[0.08, 2.5, 0.12]} />
            <meshBasicMaterial color="#1a1428" />
          </mesh>
        )
      })}

      {/* brass portal ring facing plaza approach — reads as bank entrance */}
      <group position={[0, 1.15, 2.15]} rotation={[0.15, 0, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.72, 0.05, 10, 28]} />
          <meshStandardMaterial color="#c9a227" metalness={0.85} roughness={0.22} emissive="#c9a227" emissiveIntensity={0.35} />
        </mesh>
        <mesh ref={portalGlow} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.58, 0.03, 8, 24]} />
          <meshBasicMaterial color="#2de2e6" transparent opacity={0.4} depthWrite={false} toneMapped={false} />
        </mesh>
        <group ref={portal}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.28, 0.035, 8, 20]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
          <mesh>
            <boxGeometry args={[0.42, 0.04, 0.04]} />
            <meshBasicMaterial color="#39ff14" toneMapped={false} />
          </mesh>
        </group>
        {/* threshold slab */}
        <mesh position={[0, -0.95, 0.15]}>
          <boxGeometry args={[1.5, 0.08, 0.55]} />
          <meshStandardMaterial color="#12101a" metalness={0.4} roughness={0.4} />
        </mesh>
        <mesh position={[0, -0.9, 0.15]}>
          <boxGeometry args={[1.52, 0.02, 0.04]} />
          <meshBasicMaterial color="#f9c80e" toneMapped={false} />
        </mesh>
      </group>

      <mesh ref={glow} position={[0, 0.05, 0]} scale={[1, 1.38, 1]}>
        <sphereGeometry args={[2.82, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshBasicMaterial color="#ffe9a0" transparent opacity={0.28} depthWrite={false} />
      </mesh>

      {lights && <pointLight position={[0, 2.6, 0]} intensity={1.6} color="#fff0b0" distance={16} />}

      {crystals.map((p, i) => (
        <Crystal key={i} position={p} scale={0.85 + (i % 3) * 0.12} />
      ))}

      {showHolo && <VaultHologram desk={desk} workers={workers} />}
    </group>
  )
}
