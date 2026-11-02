import { useRef, type RefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, MeshStandardMaterial } from 'three'
import type { BotPose } from '../data/botPose'

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

/** Slim two-finger gripper. At the desk the left hand taps keys and the right clicks. */
function Grip({ work = false, side = 1 }: { work?: boolean; side?: -1 | 1 }) {
  const ref = useRef<Group>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!ref.current) return
    if (work && side === -1) {
      ref.current.rotation.x = -0.55 + Math.sin(t * 14) * 0.22
      ref.current.rotation.z = Math.sin(t * 9.5) * 0.08
      return
    }
    if (work) {
      const click = Math.pow(Math.max(0, Math.sin(t * 1.65)), 8)
      ref.current.rotation.x = -0.4 - click * 0.45
      ref.current.rotation.z = Math.sin(t * 1.25) * 0.05
      return
    }
    ref.current.rotation.z = Math.sin(t * 2.8) * 0.16
    ref.current.rotation.x = Math.sin(t * 1.9) * 0.1
  })
  return (
    <group ref={ref} position={[0, 0, 0]}>
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

function Antenna({
  bulb,
  accent,
}: {
  bulb: RefObject<MeshStandardMaterial | null>
  accent: string
}) {
  const ref = useRef<Group>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!ref.current) return
    ref.current.rotation.z = Math.sin(t * 1.65) * 0.18
    ref.current.rotation.x = Math.cos(t * 1.15) * 0.1
  })
  return (
    <group ref={ref}>
      <mesh position={[0, 0.07, 0]}>
        <cylinderGeometry args={[0.008, 0.008, 0.14, 8]} />
        <meshBasicMaterial color="#f2fdff" toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.16, 0]}>
        <sphereGeometry args={[0.036, 16, 16]} />
        <meshStandardMaterial ref={bulb} color={accent} emissive={accent} emissiveIntensity={1.7} roughness={0.2} metalness={0.35} />
      </mesh>
    </group>
  )
}

type ArmPose = BotPose

function Arm({ side, pose, work = false }: { side: -1 | 1; pose: ArmPose; work?: boolean }) {
  const ref = useRef<Group>(null)
  const fore = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!ref.current) return

    if (work) {
      // -2.1 pitches the limb onto the desktop (same family as the old typing pose).
      const pace = pose === 'losing' ? 0.45 : pose === 'winning' ? 1.2 : pose === 'trading' ? 1.1 : 0.75
      if (side === -1) {
        ref.current.rotation.x = -2.2 + Math.sin(t * 7.5 * pace) * 0.05
        ref.current.rotation.y = 0.48
        ref.current.rotation.z = 0.22
        if (fore.current) fore.current.rotation.x = -0.35 + Math.sin(t * 12 * pace) * 0.12
      } else {
        const sweep = Math.sin(t * 1.35) * 0.1
        ref.current.rotation.x = -2.12 + Math.cos(t * 1.05) * 0.05
        ref.current.rotation.y = -0.5 + sweep
        ref.current.rotation.z = -0.18
        if (fore.current) fore.current.rotation.x = -0.28 + Math.sin(t * 1.6) * 0.06
      }
      return
    }

    if (pose === 'trading') {
      const type = Math.sin(t * 7.2 + side * 1.7) * 0.07
      ref.current.rotation.z = -side * 0.1 + Math.sin(t * 1.4 + side) * 0.04
      ref.current.rotation.x = -2.2 + Math.sin(t * 0.95) * 0.05
      if (fore.current) fore.current.rotation.x = -0.05 + type
      return
    }
    if (pose === 'researching') {
      const scan = Math.sin(t * 1.8 + side) * 0.1
      ref.current.rotation.z = -side * 0.18 + Math.sin(t * 1.2 + side) * 0.04
      ref.current.rotation.x = -1.85 + scan
      if (fore.current) fore.current.rotation.x = -0.35 + Math.sin(t * 2.4 + side) * 0.1
      return
    }
    if (pose === 'winning') {
      const lift = Math.sin(t * 2.4 + side) * 0.1
      ref.current.rotation.z = -side * 1.05 - side * lift
      ref.current.rotation.x = -0.22 + Math.sin(t * 1.1 + side) * 0.06
      if (fore.current) fore.current.rotation.x = -0.35 + Math.sin(t * 2.6 + side) * 0.08
      return
    }
    if (pose === 'losing') {
      const sag = Math.sin(t * 1.35 + side) * 0.06
      ref.current.rotation.z = -side * 0.35 + sag
      ref.current.rotation.x = -1.15 + Math.sin(t * 0.9 + side) * 0.07
      if (fore.current) fore.current.rotation.x = -0.55 + Math.sin(t * 2.2 + side) * 0.1
      return
    }
    // waiting — still shifting weight and looking over the desk
    const breath = Math.sin(t * 1.25 + side) * 0.07
    ref.current.rotation.z = -side * 0.55 + breath
    ref.current.rotation.x = -0.85 + Math.sin(t * 0.8 + side) * 0.08
    if (fore.current) fore.current.rotation.x = -0.5 + Math.sin(t * 2.1 + side * 1.3) * 0.1
  })

  const trading = pose === 'trading'
  return (
    <group
      ref={ref}
      position={[side * 0.3, 0.78, 0]}
      rotation={[trading ? -2.2 : -0.85, 0, trading ? -side * 0.1 : -side * 0.55]}
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
      <group ref={fore} position={[0, 0.34, 0]} rotation={[trading ? -0.05 : -0.5, 0, 0]}>
        <mesh position={[0, 0.15, 0]}>
          <cylinderGeometry args={[0.038, 0.05, 0.36, 16]} />
          <meshStandardMaterial {...shell(0.28)} />
        </mesh>
        <mesh position={[0, 0.32, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.048, 0.006, 8, 18]} />
          <meshBasicMaterial color="#f4fdff" toneMapped={false} />
        </mesh>
        <group position={[0, 0.34, 0]}>
          <Grip work={work} side={side} />
        </group>
      </group>
    </group>
  )
}

/** Thighs toward the desk, shins down beside the chair, clear of the desktop. */
function SeatedLegs() {
  return (
    <>
      {([-1, 1] as const).map((side) => (
        <group key={side} position={[side * 0.12, 0.16, 0.02]}>
          <mesh position={[0, -0.05, -0.13]} rotation={[-1.15, 0, side * 0.08]}>
            <capsuleGeometry args={[0.052, 0.2, 4, 8]} />
            <meshStandardMaterial {...shell(0.12)} />
          </mesh>
          <mesh position={[side * 0.015, -0.24, -0.24]} rotation={[0.18, 0, side * 0.05]}>
            <capsuleGeometry args={[0.044, 0.16, 4, 8]} />
            <meshStandardMaterial {...shell(0.1)} />
          </mesh>
        </group>
      ))}
    </>
  )
}

/**
 * Desk bot seen from behind. Slim shell: dome helmet, yellow ear disks,
 * antenna bulb, and a narrow back plate with a white cross and green bars.
 * Poses: trading / waiting / winning / losing / researching.
 */
export function BotFigure({
  pose = 'waiting',
  seated = true,
  deskWork = false,
}: {
  pose?: BotPose
  seated?: boolean
  /** Seated at the office desk: hands stay on the keyboard and mouse. */
  deskWork?: boolean
}) {
  const body = useRef<Group>(null)
  const torso = useRef<Group>(null)
  const head = useRef<Group>(null)
  const bulb = useRef<MeshStandardMaterial>(null)
  const anchor: [number, number, number] = deskWork ? [0, 0.34, 0.98] : seated ? [0, 0, 0.42] : [0, 0.22, 0]

  const accent =
    pose === 'winning' ? '#39ff14' : pose === 'losing' ? '#ff2a6d' : pose === 'trading' ? '#2de2e6' : '#f9c80e'

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (body.current) {
      let bob = Math.sin(t * 1.25) * 0.012
      if (pose === 'trading') bob = Math.sin(t * 1.6) * 0.014
      if (pose === 'winning') bob = Math.sin(t * 2.2) * 0.018
      if (pose === 'losing') bob = Math.sin(t * 0.9) * 0.01
      if (pose === 'researching') bob = Math.sin(t * 1.3) * 0.012
      body.current.position.y = anchor[1] + bob
      const sway = deskWork ? 0.006 : 0.014
      body.current.position.x = anchor[0] + Math.sin(t * 0.55) * sway
      body.current.rotation.y = Math.sin(t * 0.42) * (deskWork ? 0.03 : 0.055)
      body.current.rotation.z = Math.sin(t * 0.72) * 0.016
      const breathe = 1 + Math.sin(t * 1.35) * 0.01
      body.current.scale.set(1, breathe, 1)
    }
    if (torso.current) {
      if (pose === 'losing') {
        torso.current.rotation.x = deskWork ? 0.1 : 0.28
      } else if (pose === 'researching') {
        torso.current.rotation.x = -0.12 + Math.sin(t * 1.4) * 0.03
      } else if (pose === 'winning') {
        torso.current.rotation.x = -0.06
      } else {
        torso.current.rotation.x = 0
      }
    }
    if (head.current) {
      const look = Math.sin(t * 0.62) * 0.2
      const nod = Math.sin(t * 0.48 + 0.6) * 0.06
      const tilt = Math.sin(t * 0.8) * 0.04
      const deskNod = deskWork ? -0.14 : 0
      if (pose === 'losing') {
        head.current.rotation.x = (deskWork ? 0.05 : 0.22) + nod
        head.current.rotation.y = look * 0.55
      } else if (pose === 'researching') {
        head.current.rotation.y = look
        head.current.rotation.x = -0.08 + nod + deskNod
      } else if (pose === 'trading') {
        head.current.rotation.x = -0.1 + nod + deskNod
        head.current.rotation.y = look * 0.7
      } else if (pose === 'winning') {
        head.current.rotation.x = -0.06 + nod + deskNod
        head.current.rotation.y = look
      } else {
        head.current.rotation.x = nod + deskNod
        head.current.rotation.y = look
      }
      head.current.rotation.z = tilt
    }
    if (bulb.current) {
      const base = pose === 'winning' ? 2.1 : pose === 'losing' ? 0.9 : 1.5
      bulb.current.emissiveIntensity = base + Math.sin(t * 3.2) * 0.35
      bulb.current.color.set(accent)
      bulb.current.emissive.set(accent)
    }
  })

  return (
    <group ref={body} position={anchor}>
      <group ref={torso}>
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

        <group ref={head} position={[0, 1.02, 0]}>
          <mesh position={[0, 0, 0.02]}>
            <cylinderGeometry args={[0.055, 0.07, 0.1, 16]} />
            <meshStandardMaterial {...shell(0.2)} />
          </mesh>
          <mesh position={[0, 0.26, 0.04]} scale={[1, 0.94, 0.96]}>
            <sphereGeometry args={[0.24, 32, 24]} />
            <meshStandardMaterial color="#e9fdff" emissive="#8eecff" emissiveIntensity={0.42} roughness={0.1} metalness={0.48} />
          </mesh>
          <mesh position={[0, 0.18, -0.12]} rotation={[0.55, 0, 0]}>
            <boxGeometry args={[0.2, 0.028, 0.02]} />
            <meshStandardMaterial color="#061018" metalness={0.8} roughness={0.18} />
          </mesh>

          <group position={[0, 0.48, 0.04]}>
            <Antenna bulb={bulb} accent={accent} />
          </group>

          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.25, 0.24, 0.06]}>
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
        </group>

        <Arm side={-1} pose={pose} work={deskWork} />
        <Arm side={1} pose={pose} work={deskWork} />
      </group>

      {deskWork ? (
        <SeatedLegs />
      ) : (
        ([-0.1, 0.1] as const).map((x) => (
          <mesh key={x} position={[x, 0.02, 0.04]} rotation={[0.55, 0, x > 0 ? -0.05 : 0.05]}>
            <cylinderGeometry args={[0.05, 0.045, 0.32, 14]} />
            <meshStandardMaterial {...shell(0.12)} />
          </mesh>
        ))
      )}
    </group>
  )
}
