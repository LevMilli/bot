import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Mesh } from 'three'

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

export function Vault({ lights = true }: { lights?: boolean }) {
  const dome = useRef<Mesh>(null)
  const glow = useRef<Mesh>(null)

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
  })

  const crystals: [number, number, number][] = []
  for (let i = 0; i < 14; i++) {
    const a = (i / 14) * Math.PI * 2 + 0.2
    const r = 3.05 + (i % 3) * 0.18
    crystals.push([Math.cos(a) * r, 0.42, Math.sin(a) * r])
  }

  return (
    <group position={[0, 0, 5.2]}>
      {/* raised pad */}
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[3.35, 64]} />
        <meshStandardMaterial color="#08061a" emissive="#1a6cff" emissiveIntensity={0.25} />
      </mesh>
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[3.2, 3.45, 64]} />
        <meshBasicMaterial color="#f9c80e" transparent opacity={0.92} />
      </mesh>
      <mesh position={[0, 0.045, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[2.55, 2.7, 64]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.55} />
      </mesh>

      <mesh ref={dome} position={[0, 0.05, 0]} scale={[1, 1.38, 1]}>
        <sphereGeometry args={[2.55, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2]} />
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
      {Array.from({ length: 10 }).map((_, i) => {
        const a = (i / 10) * Math.PI * 2
        return (
          <mesh
            key={i}
            position={[Math.cos(a) * 2.42, 1.35, Math.sin(a) * 2.42]}
            rotation={[0, -a, 0.08]}
          >
            <boxGeometry args={[0.08, 2.5, 0.12]} />
            <meshStandardMaterial color="#1a1428" metalness={0.4} roughness={0.45} />
          </mesh>
        )
      })}

      <mesh ref={glow} position={[0, 0.05, 0]} scale={[1, 1.38, 1]}>
        <sphereGeometry args={[2.82, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshBasicMaterial color="#ffe9a0" transparent opacity={0.28} depthWrite={false} />
      </mesh>

      {lights && (
        <>
          <pointLight position={[0, 2.6, 0]} intensity={3.2} color="#fff0b0" distance={22} />
          <pointLight position={[0, 1.2, 1.5]} intensity={1.4} color="#ffe08a" distance={10} />
        </>
      )}

      {crystals.map((p, i) => (
        <Crystal key={i} position={p} scale={0.85 + (i % 3) * 0.12} />
      ))}
    </group>
  )
}
