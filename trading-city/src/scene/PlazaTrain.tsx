import { useMemo, useRef, type MutableRefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import type { Group, Mesh } from 'three'
import { RAIL_GAUGE, RAIL_R, RAIL_Z_OFF } from './plazaLayout'

const RAIL_Y = 0.2
const Z_OFF = RAIL_Z_OFF
const TIE_COUNT = 36
const SEGMENTS = 56
/** Fixed magnetic rings around the guideway. They stay put and trace the loop. */
const PAD_COUNT = 28
/** How close the consist must be before a ring lights. */
const PAD_LIGHT_RAD = 0.1
/** Fade-out after the consist leaves a ring. */
const PAD_FADE_SEC = 0.85

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** One purple livery. Bogie spacing keeps both ends on the guideway. */
const CARS = [
  { arc: 0, role: 'lead' as const, len: 2.05 },
  { arc: 2.08, role: 'mid' as const, len: 1.92 },
  { arc: 4.08, role: 'mid' as const, len: 1.92 },
  { arc: 6.04, role: 'tail' as const, len: 1.95 },
]
/** Gap from the rail head. Every car uses this same lift. */
const HOVER = 0.11

const SHELL = '#efe7ff'
const SHELL_DEEP = '#7c3aed'
const BELLY = '#3b0764'
const GLOW = '#c084fc'
const GLOW_HOT = '#f3e8ff'
const GLASS = '#07040e'

function railPoint(angle: number, radius: number) {
  return {
    x: Math.cos(angle) * radius,
    z: Math.sin(angle) * radius + Z_OFF,
  }
}

function wrapPi(d: number) {
  let x = d
  while (x > Math.PI) x -= Math.PI * 2
  while (x < -Math.PI) x += Math.PI * 2
  return x
}

/**
 * Rigid car whose bogies sit on the loop. The body is the chord between them,
 * so the ends stay over the rails instead of swinging inside the curve.
 * Forward is local −X, toward increasing angle.
 */
function poseOnRail(angle: number, radius: number, bogie: number) {
  const da = bogie / radius
  const front = railPoint(angle + da, radius)
  const rear = railPoint(angle - da, radius)
  const dx = front.x - rear.x
  const dz = front.z - rear.z
  return {
    x: (front.x + rear.x) / 2,
    z: (front.z + rear.z) / 2,
    rotY: Math.atan2(dz, -dx),
  }
}

const shellMat = {
  color: SHELL,
  metalness: 0.22,
  roughness: 0.32,
  emissive: SHELL_DEEP,
  emissiveIntensity: 0.42,
} as const

const glassMat = {
  color: GLASS,
  metalness: 0.72,
  roughness: 0.08,
  emissive: '#1a1030',
  emissiveIntensity: 0.08,
} as const

function BulletCar({ role, len }: { role: 'lead' | 'mid' | 'tail'; len: number }) {
  const half = len / 2
  const bodyLen = len
  const bodyShift = 0
  // Tail glass reaches the point the same distance the nose glass reaches the front.
  const rearExtra = role === 'tail' ? 0.16 : 0.18
  const frontExtra = role === 'lead' ? 0.16 : 0
  const glassLen = bodyLen + rearExtra + frontExtra
  const glassX = bodyShift + (rearExtra - frontExtra) / 2
  return (
    <group>
      <mesh position={[bodyShift, 0.1, 0]}>
        <boxGeometry args={[bodyLen, 0.045, 0.36]} />
        <meshStandardMaterial
          color={BELLY}
          metalness={0.3}
          roughness={0.4}
          emissive="#4c1d95"
          emissiveIntensity={0.2}
        />
      </mesh>
      <mesh position={[bodyShift, 0.22, 0]}>
        <boxGeometry args={[bodyLen, 0.18, 0.4]} />
        <meshStandardMaterial {...shellMat} />
      </mesh>
      <mesh position={[bodyShift, 0.33, 0]}>
        <boxGeometry args={[bodyLen * 0.98, 0.05, 0.34]} />
        <meshStandardMaterial
          color="#f5f3ff"
          metalness={0.2}
          roughness={0.28}
          emissive={SHELL_DEEP}
          emissiveIntensity={0.28}
        />
      </mesh>
      {/* Dark glass channel down the roof. */}
      <mesh position={[glassX, 0.362, 0]}>
        <boxGeometry args={[glassLen, 0.014, 0.12]} />
        <meshStandardMaterial {...glassMat} />
      </mesh>

      {([-1, 1] as const).map((side) => (
        <group key={side}>
          <mesh position={[glassX, 0.23, side * 0.208]}>
            <boxGeometry args={[glassLen, 0.11, 0.016]} />
            <meshStandardMaterial {...glassMat} />
          </mesh>
          <mesh position={[glassX, 0.155, side * 0.214]}>
            <boxGeometry args={[glassLen, 0.012, 0.008]} />
            <meshBasicMaterial color={GLOW} toneMapped={false} />
          </mesh>
        </group>
      ))}

      {role === 'lead' && (
        <group>
          <mesh position={[-half - 0.9, 0.2, 0]} rotation={[0, 0, Math.PI / 2]} scale={[0.5, 1, 1.05]}>
            <coneGeometry args={[0.22, 2.15, 16]} />
            <meshStandardMaterial {...shellMat} />
          </mesh>
          <mesh position={[-half - 0.62, 0.11, 0]} rotation={[0, 0, Math.PI / 2]} scale={[0.32, 1, 0.9]}>
            <coneGeometry args={[0.18, 1.45, 12]} />
            <meshStandardMaterial
              color={SHELL_DEEP}
              metalness={0.2}
              roughness={0.34}
              emissive="#5b21b6"
              emissiveIntensity={0.35}
            />
          </mesh>
          <mesh position={[-half - 0.42, 0.26, 0]} rotation={[0, 0, 0.5]}>
            <boxGeometry args={[0.85, 0.04, 0.28]} />
            <meshStandardMaterial {...glassMat} />
          </mesh>
          <mesh position={[-half - 0.12, 0.33, 0]} rotation={[0, 0, 0.32]}>
            <boxGeometry args={[0.42, 0.012, 0.1]} />
            <meshStandardMaterial {...glassMat} />
          </mesh>
          <mesh position={[-half - 1.92, 0.2, 0]}>
            <boxGeometry args={[0.04, 0.03, 0.06]} />
            <meshBasicMaterial color={GLOW_HOT} toneMapped={false} />
          </mesh>
        </group>
      )}

      {/* Exact mirror of the nose. Tip points to +X. */}
      {role === 'tail' && (
        <group>
          <mesh position={[half + 0.9, 0.2, 0]} rotation={[0, 0, -Math.PI / 2]} scale={[0.5, 1, 1.05]}>
            <coneGeometry args={[0.22, 2.15, 16]} />
            <meshStandardMaterial {...shellMat} />
          </mesh>
          <mesh position={[half + 0.62, 0.11, 0]} rotation={[0, 0, -Math.PI / 2]} scale={[0.32, 1, 0.9]}>
            <coneGeometry args={[0.18, 1.45, 12]} />
            <meshStandardMaterial
              color={SHELL_DEEP}
              metalness={0.2}
              roughness={0.34}
              emissive="#5b21b6"
              emissiveIntensity={0.35}
            />
          </mesh>
          <mesh position={[half + 0.42, 0.26, 0]} rotation={[0, 0, -0.5]}>
            <boxGeometry args={[0.85, 0.04, 0.28]} />
            <meshStandardMaterial {...glassMat} />
          </mesh>
          <mesh position={[half + 0.12, 0.33, 0]} rotation={[0, 0, -0.32]}>
            <boxGeometry args={[0.42, 0.012, 0.1]} />
            <meshStandardMaterial {...glassMat} />
          </mesh>
          <mesh position={[half + 1.92, 0.2, 0]}>
            <boxGeometry args={[0.04, 0.03, 0.06]} />
            <meshBasicMaterial color={GLOW_HOT} toneMapped={false} />
          </mesh>
        </group>
      )}

      {role !== 'tail' && (
        <mesh position={[half + 0.09, 0.22, 0]}>
          <boxGeometry args={[0.22, 0.14, 0.36]} />
          <meshStandardMaterial {...shellMat} />
        </mesh>
      )}
    </group>
  )
}

/**
 * Fixed pads on the guideway. The train lights each pad as it passes;
 * pads pulse while lit, then fade out when the consist leaves.
 */
function MaglevPads({
  radius,
  y,
  trainAngle,
  reduced,
}: {
  radius: number
  y: number
  trainAngle: MutableRefObject<number>
  reduced: boolean
}) {
  const pads = useMemo(() => {
    const out: { angle: number; x: number; z: number }[] = []
    for (let i = 0; i < PAD_COUNT; i++) {
      const a = (i / PAD_COUNT) * Math.PI * 2
      const p = railPoint(a, radius)
      out.push({ angle: a, x: p.x, z: p.z })
    }
    return out
  }, [radius])

  const glowRefs = useRef<(Mesh | null)[]>([])
  const coreRefs = useRef<(Mesh | null)[]>([])
  const energy = useRef(new Float32Array(PAD_COUNT))
  const carAngles = useRef(new Float32Array(CARS.length))

  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime()
    const a0 = trainAngle.current
    for (let i = 0; i < CARS.length; i++) {
      carAngles.current[i] = a0 - CARS[i].arc / radius
    }
      const pulse = reduced ? 0.85 : 0.55 + 0.45 * Math.sin(t * 7.4)
      for (let i = 0; i < PAD_COUNT; i++) {
        let nearest = Math.PI
        for (let c = 0; c < CARS.length; c++) {
          const d = Math.abs(wrapPi(pads[i].angle - carAngles.current[c]))
          if (d < nearest) nearest = d
        }
        const target = nearest < PAD_LIGHT_RAD ? 1 - nearest / PAD_LIGHT_RAD : 0
        const cur = energy.current[i]
        const next =
          target > cur
            ? Math.min(1, cur + dt * 8)
            : Math.max(0, cur - dt / PAD_FADE_SEC)
        energy.current[i] = next
        const lit = next * pulse
        const glow = glowRefs.current[i]
        const core = coreRefs.current[i]
        if (glow) {
          glow.visible = true
          const mat = glow.material as { opacity: number }
          mat.opacity = 0.38 + lit * 0.62
          glow.scale.setScalar(1 + lit * 0.05)
        }
        if (core) {
          core.visible = true
          const mat = core.material as { opacity: number }
          mat.opacity = 0.08 + lit * 0.9
          core.scale.setScalar(1 + lit * 0.04)
        }
      }
  })

  return (
    <group>
      {pads.map((p, i) => (
        <group key={i} position={[p.x, y, p.z]}>
          <mesh
            ref={(el) => {
              glowRefs.current[i] = el
            }}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <torusGeometry args={[0.3, 0.016, 8, 28]} />
            <meshBasicMaterial color={GLOW} toneMapped={false} transparent opacity={0.38} depthWrite={false} />
          </mesh>
          <mesh
            ref={(el) => {
              coreRefs.current[i] = el
            }}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <torusGeometry args={[0.16, 0.008, 6, 20]} />
            <meshBasicMaterial color={GLOW_HOT} toneMapped={false} transparent opacity={0.08} depthWrite={false} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

/** Sleek purple maglev. Bogies stay on the loop. The consist lifts as one piece. */
export function PlazaTrain({
  radius = RAIL_R,
  y = RAIL_Y,
  speed = 0.28,
}: {
  radius?: number
  y?: number
  speed?: number
}) {
  const carRefs = useRef<(Group | null)[]>([])
  const bobRefs = useRef<(Group | null)[]>([])
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const angle = useRef(1.15)

  useFrame(({ clock }, dt) => {
    if (!reduced) angle.current = (angle.current + dt * speed) % (Math.PI * 2)
    const t = clock.getElapsedTime()
    const a0 = angle.current
    for (let i = 0; i < CARS.length; i++) {
      const g = carRefs.current[i]
      if (!g) continue
      const car = CARS[i]
      const a = a0 - car.arc / radius
      const pose = poseOnRail(a, radius, car.len * 0.32)
      g.position.set(pose.x, y, pose.z)
      g.rotation.y = pose.rotY
      const bob = bobRefs.current[i]
      if (!bob) continue
      const lift = reduced ? HOVER : HOVER + Math.sin(t * 1.35) * 0.011
      bob.position.y = lift
      bob.rotation.z = 0
    }
  })

  return (
    <group raycast={() => null}>
      {/* Pads sit on the guideway deck — lit only while the consist is overhead. */}
      <MaglevPads radius={radius} y={0.03} trainAngle={angle} reduced={reduced} />
      {CARS.map((car, i) => {
        const a = 1.15 - car.arc / radius
        const pose = poseOnRail(a, radius, car.len * 0.32)
        return (
          <group
            key={car.role + i}
            ref={(el) => {
              carRefs.current[i] = el
            }}
            position={[pose.x, y, pose.z]}
            rotation={[0, pose.rotY, 0]}
          >
            <group
              ref={(el) => {
                bobRefs.current[i] = el
              }}
              position={[0, HOVER, 0]}
            >
              <BulletCar role={car.role} len={car.len} />
            </group>
          </group>
        )
      })}
    </group>
  )
}

/** Maglev guideway on the same loop — dark beam, neon rails, purple center. */
export function PlazaRailroad({
  radius = RAIL_R,
  y = 0.06,
}: {
  radius?: number
  y?: number
}) {
  const ties = useMemo(() => {
    const out: { x: number; z: number; rot: number }[] = []
    for (let i = 0; i < TIE_COUNT; i++) {
      const a = (i / TIE_COUNT) * Math.PI * 2
      out.push({
        x: Math.cos(a) * radius,
        z: Math.sin(a) * radius + Z_OFF,
        rot: -a,
      })
    }
    return out
  }, [radius])

  const plates = useMemo(() => {
    const out: { x: number; z: number; rot: number }[] = []
    const n = 16
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + 0.04
      out.push({
        x: Math.cos(a) * radius,
        z: Math.sin(a) * radius + Z_OFF,
        rot: -a,
      })
    }
    return out
  }, [radius])

  const signals = useMemo(() => {
    const out: [number, number, number, number][] = []
    const n = 6
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2
      const r = radius + 0.95
      out.push([Math.cos(a) * r, 0, Math.sin(a) * r + Z_OFF, -a])
    }
    return out
  }, [radius])

  const stators = useMemo(() => {
    const out: { x: number; z: number; rot: number }[] = []
    const n = 28
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + Math.PI / n
      out.push({
        x: Math.cos(a) * radius,
        z: Math.sin(a) * radius + Z_OFF,
        rot: -a,
      })
    }
    return out
  }, [radius])

  const innerR = radius - RAIL_GAUGE / 2
  const outerR = radius + RAIL_GAUGE / 2

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.02, Z_OFF]}>
        <ringGeometry args={[radius - 0.9, radius + 0.9, SEGMENTS]} />
        <meshBasicMaterial color="#0c0e14" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.005, Z_OFF]}>
        <ringGeometry args={[radius - 0.68, radius + 0.68, SEGMENTS]} />
        <meshBasicMaterial color="#16141e" />
      </mesh>

      {ties.map((t, i) => (
        <mesh key={i} position={[t.x, y + 0.03, t.z]} rotation={[0, t.rot, 0]}>
          <boxGeometry args={[1.15, 0.05, 0.16]} />
          <meshBasicMaterial color={i % 2 === 0 ? '#1c2030' : '#141820'} />
        </mesh>
      ))}

      {/* Reaction plate sits just above the ties, inside the guide rails. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y + 0.062, Z_OFF]}>
        <ringGeometry args={[radius - 0.3, radius + 0.3, SEGMENTS]} />
        <meshBasicMaterial color="#14121c" />
      </mesh>
      {/* Stator poles between the magnetic rings — linear-motor teeth, clear of the rails. */}
      {stators.map((s, i) => (
        <group key={`st-${i}`} position={[s.x, y + 0.085, s.z]} rotation={[0, s.rot, 0]}>
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[side * 0.16, 0, 0]}>
              <boxGeometry args={[0.07, 0.028, 0.1]} />
              <meshBasicMaterial color={i % 2 === 0 ? '#2a2438' : '#1c1828'} />
            </mesh>
          ))}
        </group>
      ))}

      {/* Twin guide rails stay cyan / gold. A slim purple beam runs the center. */}
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.045, 8, SEGMENTS]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.045, 8, SEGMENTS]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius, 0.014, 6, SEGMENTS]} />
        <meshBasicMaterial color="#b967ff" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.14, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.018, 6, SEGMENTS]} />
        <meshBasicMaterial color="#d8fbff" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.14, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.018, 6, SEGMENTS]} />
        <meshBasicMaterial color="#ffe08a" toneMapped={false} />
      </mesh>

      {plates.map((p, i) => (
        <group key={`pl-${i}`} position={[p.x, y + 0.1, p.z]} rotation={[0, p.rot, 0]}>
          <mesh position={[0, 0.02, -RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.18, 0.05, 0.1]} />
            <meshBasicMaterial color="#1a2438" />
          </mesh>
          <mesh position={[0, 0.05, -RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.08, 0.03, 0.06]} />
            <meshBasicMaterial color="#2de2e6" toneMapped={false} />
          </mesh>
          <mesh position={[0, 0.02, RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.18, 0.05, 0.1]} />
            <meshBasicMaterial color="#1a2438" />
          </mesh>
          <mesh position={[0, 0.05, RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.08, 0.03, 0.06]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
          <mesh position={[0, 0.03, 0]}>
            <boxGeometry args={[0.1, 0.025, 0.08]} />
            <meshBasicMaterial color="#b967ff" toneMapped={false} />
          </mesh>
        </group>
      ))}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, Z_OFF]}>
        <ringGeometry args={[radius - 0.34, radius + 0.34, 48]} />
        <meshBasicMaterial color="#6d28d9" transparent opacity={0.05} depthWrite={false} />
      </mesh>

      {signals.map(([x, , z, rot], i) => (
        <group key={i} position={[x, 0, z]} rotation={[0, rot, 0]} raycast={() => null}>
          <mesh position={[0, 0.4, 0]}>
            <cylinderGeometry args={[0.035, 0.045, 0.8, 6]} />
            <meshBasicMaterial color="#1a2438" />
          </mesh>
          <mesh position={[0, 0.84, 0]}>
            <boxGeometry args={[0.12, 0.16, 0.07]} />
            <meshBasicMaterial color="#101820" />
          </mesh>
          <mesh position={[0, 0.86, 0.05]}>
            <sphereGeometry args={[0.045, 8, 8]} />
            <meshBasicMaterial color={i % 2 === 0 ? '#c084fc' : '#6d28d9'} toneMapped={false} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

export { RAIL_GAUGE }
