import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, MeshStandardMaterial } from 'three'

const SHELL = '#d7fbff'
const JOINT = '#071820'

function shell(emissiveIntensity = 0.22) {
  return {
    color: SHELL,
    emissive: '#1aa8d8',
    emissiveIntensity,
    roughness: 0.16,
    metalness: 0.62,
  }
}

/** Slim two-finger gripper on a small cuff, so the hand reads as one piece. */
function Grip() {
  return (
    <group position={[0, 0.02, 0]}>
      <mesh>
        <sphereGeometry args={[0.04, 14, 14]} />
        <meshStandardMaterial {...shell(0.34)} />
      </mesh>
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[side * 0.03, 0.07, 0.01]} rotation={[0.2, 0, side * 0.22]}>
          <boxGeometry args={[0.016, 0.1, 0.018]} />
          <meshStandardMaterial {...shell(0.4)} />
        </mesh>
      ))}
    </group>
  )
}

function Arm({ side, pose }: { side: -1 | 1; pose: 'celebrate' | 'work' }) {
  const ref = useRef<Group>(null)
  const fore = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!ref.current) return
    if (pose === 'work') {
      const type = Math.sin(t * 6.2 + side * 1.7) * 0.04
      ref.current.rotation.z = -side * 0.12
      ref.current.rotation.x = -2.15
      if (fore.current) fore.current.rotation.x = -0.08 + type
      return
    }
    const lift = Math.sin(t * 2.05 + side) * 0.04
    ref.current.rotation.z = -side * 1.02 + -side * lift
    ref.current.rotation.x = -0.28
    if (fore.current) fore.current.rotation.x = -0.42
  })

  const working = pose === 'work'
  return (
    <group
      ref={ref}
      position={[side * 0.3, 0.78, 0]}
      rotation={[working ? -2.15 : -0.28, 0, working ? -side * 0.12 : -side * 1.02]}
    >
      <mesh position={[0, 0.17, 0]}>
        <cylinderGeometry args={[0.046, 0.054, 0.36, 16]} />
        <meshStandardMaterial {...shell(0.28)} />
      </mesh>
      <mesh position={[0, 0.34, 0]}>
        <sphereGeometry args={[0.058, 16, 16]} />
        <meshStandardMaterial {...shell(0.2)} />
      </mesh>
      <mesh position={[0, 0.34, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.064, 0.007, 8, 22]} />
        <meshStandardMaterial color="#123044" metalness={0.75} roughness={0.22} />
      </mesh>
      <group ref={fore} position={[0, 0.34, 0]} rotation={[working ? -0.08 : -0.42, 0, 0]}>
        <mesh position={[0, 0.15, 0]}>
          <cylinderGeometry args={[0.038, 0.05, 0.36, 16]} />
          <meshStandardMaterial {...shell(0.28)} />
        </mesh>
        <mesh position={[0, 0.32, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.048, 0.006, 8, 18]} />
          <meshBasicMaterial color="#f4fdff" toneMapped={false} />
        </mesh>
        <group position={[0, 0.34, 0]}>
          <Grip />
        </group>
      </group>
    </group>
  )
}

/**
 * Desk bot seen from behind. Slim shell: dome helmet, yellow ear disks,
 * antenna bulb, and a narrow back plate with a white cross and green bars.
 * `celebrate` holds the arms in a V. `work` reaches them toward a console.
 * `seated` parks the figure in the desk chair; otherwise it stands on y=0.
 */
export function BotFigure({
  celebrating = true,
  pose = 'celebrate',
  seated = true,
}: {
  celebrating?: boolean
  pose?: 'celebrate' | 'work'
  seated?: boolean
}) {
  const body = useRef<Group>(null)
  const bulb = useRef<MeshStandardMaterial>(null)
  const anchor: [number, number, number] = seated ? [0, 0, 0.42] : [0, 0.22, 0]

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (body.current) {
      const bob =
        pose === 'work'
          ? Math.sin(t * 1.2) * 0.006
          : Math.sin(t * 1.5) * (celebrating ? 0.01 : 0.004)
      body.current.position.y = anchor[1] + bob
    }
    if (bulb.current) bulb.current.emissiveIntensity = 1.5 + Math.sin(t * 3.2) * 0.3
  })

  return (
    <group ref={body} position={anchor}>
      <mesh position={[0, 0.16, 0]}>
        <sphereGeometry args={[0.15, 20, 16]} />
        <meshStandardMaterial {...shell(0.16)} />
      </mesh>
      <mesh position={[0, 0.56, 0]}>
        <cylinderGeometry args={[0.2, 0.24, 0.64, 24]} />
        <meshStandardMaterial {...shell(0.18)} />
      </mesh>
      <mesh position={[0, 0.56, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.225, 0.008, 8, 28]} />
        <meshStandardMaterial color={JOINT} metalness={0.8} roughness={0.25} />
      </mesh>
      <mesh position={[0, 0.88, 0]} rotation={[0, 0, Math.PI / 2]}>
        <capsuleGeometry args={[0.062, 0.34, 6, 12]} />
        <meshStandardMaterial {...shell(0.24)} />
      </mesh>

      {/* Narrow back plate. Faces the camera (+Z), clear of the chair lumbar. */}
      <mesh position={[0, 0.58, 0.28]}>
        <boxGeometry args={[0.34, 0.56, 0.04]} />
        <meshStandardMaterial color="#05060c" roughness={0.35} metalness={0.55} />
      </mesh>
      <mesh position={[0, 0.58, 0.305]}>
        <boxGeometry args={[0.36, 0.02, 0.012]} />
        <meshStandardMaterial color="#1a2433" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.58, 0.308]}>
        <boxGeometry args={[0.045, 0.36, 0.012]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.7, 0.308]}>
        <boxGeometry args={[0.16, 0.036, 0.012]} />
        <meshBasicMaterial color="#ffffff" toneMapped={false} />
      </mesh>
      {([-0.12, 0.12] as const).map((x) => (
        <mesh key={x} position={[x, 0.58, 0.308]}>
          <boxGeometry args={[0.022, 0.4, 0.01]} />
          <meshBasicMaterial color="#39ff14" toneMapped={false} />
        </mesh>
      ))}

      <mesh position={[0, 1.02, 0.02]}>
        <cylinderGeometry args={[0.055, 0.07, 0.1, 16]} />
        <meshStandardMaterial {...shell(0.2)} />
      </mesh>
      <mesh position={[0, 1.28, 0.04]} scale={[1, 0.94, 0.96]}>
        <sphereGeometry args={[0.24, 32, 24]} />
        <meshStandardMaterial color="#e9fdff" emissive="#8eecff" emissiveIntensity={0.42} roughness={0.1} metalness={0.48} />
      </mesh>
      <mesh position={[0, 1.2, -0.12]} rotation={[0.55, 0, 0]}>
        <boxGeometry args={[0.2, 0.028, 0.02]} />
        <meshStandardMaterial color="#061018" metalness={0.8} roughness={0.18} />
      </mesh>

      <mesh position={[0, 1.54, 0.04]}>
        <cylinderGeometry args={[0.008, 0.008, 0.14, 8]} />
        <meshBasicMaterial color="#f2fdff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 1.64, 0.04]}>
        <sphereGeometry args={[0.036, 16, 16]} />
        <meshStandardMaterial ref={bulb} color="#f9c80e" emissive="#f9c80e" emissiveIntensity={1.7} roughness={0.2} metalness={0.35} />
      </mesh>

      {([-1, 1] as const).map((side) => (
        <group key={side} position={[side * 0.25, 1.26, 0.06]}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.062, 0.062, 0.028, 20]} />
            <meshStandardMaterial color="#f9c80e" emissive="#f9c80e" emissiveIntensity={0.7} roughness={0.22} metalness={0.45} />
          </mesh>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.062, 0.008, 8, 20]} />
            <meshBasicMaterial color="#39ff14" toneMapped={false} />
          </mesh>
        </group>
      ))}

      <Arm side={-1} pose={pose} />
      <Arm side={1} pose={pose} />

      {([-0.1, 0.1] as const).map((x) => (
        <mesh key={x} position={[x, 0.02, 0.04]} rotation={[0.55, 0, x > 0 ? -0.05 : 0.05]}>
          <cylinderGeometry args={[0.05, 0.045, 0.32, 14]} />
          <meshStandardMaterial {...shell(0.12)} />
        </mesh>
      ))}
    </group>
  )
}
