import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Group, Mesh } from 'three'
import { RAIL_GAUGE, RAIL_R, RAIL_Z_OFF } from './plazaLayout'

const RAIL_Y = 0.2
const Z_OFF = RAIL_Z_OFF
const TIE_COUNT = 36
const SEGMENTS = 56
const SMOKE_COUNT = 18
const SMOKE_LIFE = 2.8

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Arc-length spacing behind the loco so each car sits on the circle (not a chord). */
const CAR_ARCS = [0, 1.38, 2.65, 3.9] as const
const CAR_COLORS = ['#ff2a6d', '#2de2e6', '#b967ff', '#39ff14'] as const

/** Physical stack on the loco (no particles — trail lives in world space). */
function SmokeStack() {
  return (
    <group position={[0.22, 0.92, 0]}>
      <mesh position={[0, 0.18, 0]}>
        <cylinderGeometry args={[0.07, 0.09, 0.36, 8]} />
        <meshBasicMaterial color="#1a1e28" />
      </mesh>
      <mesh position={[0, 0.38, 0]}>
        <cylinderGeometry args={[0.1, 0.08, 0.08, 8]} />
        <meshBasicMaterial color="#2a2438" />
      </mesh>
    </group>
  )
}

/**
 * World-space smoke trail: puffs spawn at the stack tip and stay put while the
 * train moves on, so smoke hangs behind the loco along the track.
 */
function SmokeTrail({ locoRef }: { locoRef: { current: Group | null } }) {
  const puffs = useRef<(Mesh | null)[]>([])
  const ages = useRef<Float32Array>(new Float32Array(SMOKE_COUNT).fill(SMOKE_LIFE + 1))
  const spawnAcc = useRef(0)
  const next = useRef(0)
  // Stack tip in loco local space (SmokeStack sits near cabin roof).
  const tipLocal = useMemo(() => new THREE.Vector3(0.22, 1.38, 0), [])
  const tipWorld = useMemo(() => new THREE.Vector3(), [])
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const ready = useRef(false)

  useFrame((_, dt) => {
    if (reduced) return
    const loco = locoRef.current
    if (loco) {
      loco.updateWorldMatrix(true, false)
      tipWorld.copy(tipLocal).applyMatrix4(loco.matrixWorld)
      // Skip first frames until the loco matrix is off the origin.
      if (!ready.current) {
        if (tipWorld.lengthSq() > 4) ready.current = true
        else return
      }
      spawnAcc.current += dt
      if (spawnAcc.current >= 0.08) {
        spawnAcc.current = 0
        const i = next.current % SMOKE_COUNT
        next.current += 1
        const m = puffs.current[i]
        if (m) {
          m.position.set(tipWorld.x, tipWorld.y + 0.05, tipWorld.z)
          m.scale.setScalar(0.16)
          ages.current[i] = 0
          const mat = m.material as THREE.MeshBasicMaterial
          mat.opacity = 0.55
          m.visible = true
        }
      }
    }

    for (let i = 0; i < SMOKE_COUNT; i++) {
      const m = puffs.current[i]
      if (!m || !m.visible) continue
      ages.current[i] += dt
      const age = ages.current[i]
      if (age > SMOKE_LIFE) {
        m.visible = false
        continue
      }
      const t = age / SMOKE_LIFE
      // Rise + soft drift; stay in world space so the plume trails the loco.
      m.position.y += dt * 0.72
      m.scale.setScalar(0.16 + t * 0.7)
      const mat = m.material as THREE.MeshBasicMaterial
      mat.opacity = Math.max(0, 0.5 * (1 - t * t))
    }
  })

  return (
    <group>
      {Array.from({ length: SMOKE_COUNT }).map((_, i) => (
        <mesh
          key={i}
          ref={(el) => {
            puffs.current[i] = el
          }}
          visible={false}
        >
          <sphereGeometry args={[0.18, 7, 7]} />
          <meshBasicMaterial color="#d0d6e0" transparent opacity={0} depthWrite={false} />
        </mesh>
      ))}
    </group>
  )
}

function CarBody({
  color,
  loco = false,
}: {
  color: string
  loco?: boolean
}) {
  const len = loco ? 1.35 : 1.08
  const half = len / 2
  const bodyZ = 0.5
  return (
    <group>
      <mesh position={[0, 0.12, 0]}>
        <boxGeometry args={[len, 0.12, bodyZ + 0.04]} />
        <meshBasicMaterial color="#12161e" />
      </mesh>
      <mesh position={[0, 0.4, 0]}>
        <boxGeometry args={[len - 0.08, 0.48, bodyZ]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      {/* cabin / roof */}
      <mesh position={[loco ? 0.22 : 0, 0.72, 0]}>
        <boxGeometry args={[loco ? 0.62 : len - 0.18, loco ? 0.28 : 0.14, bodyZ - 0.06]} />
        <meshBasicMaterial color="#0a0e18" />
      </mesh>
      <mesh position={[0, 0.82, 0]}>
        <boxGeometry args={[len - 0.35, 0.04, 0.14]} />
        <meshBasicMaterial color="#7ef9ff" toneMapped={false} />
      </mesh>
      {/* Side windows — both sides */}
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[loco ? 0.2 : 0, 0.44, side * (bodyZ / 2 + 0.01)]}>
          <boxGeometry args={[loco ? 0.48 : len - 0.28, 0.16, 0.03]} />
          <meshBasicMaterial color="#c8f7ff" transparent opacity={0.9} toneMapped={false} />
        </mesh>
      ))}
      {loco && (
        <>
          <mesh position={[-half + 0.12, 0.3, 0]}>
            <boxGeometry args={[0.36, 0.3, bodyZ - 0.02]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
          <mesh position={[-half - 0.06, 0.1, 0]} rotation={[0, 0, -0.4]}>
            <boxGeometry args={[0.22, 0.08, bodyZ + 0.04]} />
            <meshBasicMaterial color="#2a2430" />
          </mesh>
          <mesh position={[-half - 0.08, 0.38, 0]}>
            <sphereGeometry args={[0.08, 10, 10]} />
            <meshBasicMaterial color="#fff8d8" toneMapped={false} />
          </mesh>
          <mesh position={[0.42, 0.86, 0]}>
            <boxGeometry args={[0.2, 0.05, 0.12]} />
            <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
          </mesh>
          <SmokeStack />
        </>
      )}
      {([-half + 0.24, half - 0.24] as const).map((x) =>
        ([-RAIL_GAUGE / 2, RAIL_GAUGE / 2] as const).map((z) => (
          <mesh key={`${x}-${z}`} position={[x, 0.09, z]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.09, 0.09, 0.06, 10]} />
            <meshBasicMaterial color="#1a1e28" />
          </mesh>
        )),
      )}
      <mesh position={[half + 0.02, 0.16, 0]}>
        <boxGeometry args={[0.08, 0.05, 0.05]} />
        <meshBasicMaterial color="#3a4050" />
      </mesh>
    </group>
  )
}

/** Locomotive + cars that orbit the plaza railroad forever — each car on the rail centerline. */
export function PlazaTrain({
  radius = RAIL_R,
  y = RAIL_Y,
  speed = 0.22,
}: {
  radius?: number
  y?: number
  speed?: number
}) {
  const carRefs = useRef<(Group | null)[]>([])
  const locoRef = useRef<Group | null>(null)
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const angle = useRef(0.35)

  useFrame((_, dt) => {
    if (reduced) return
    angle.current = (angle.current + dt * speed) % (Math.PI * 2)
    const a0 = angle.current
    for (let i = 0; i < CAR_ARCS.length; i++) {
      const g = carRefs.current[i]
      if (!g) continue
      const a = a0 - CAR_ARCS[i] / radius
      g.position.set(Math.cos(a) * radius, y, Math.sin(a) * radius + Z_OFF)
      g.rotation.y = -a + Math.PI / 2
    }
  })

  return (
    <group raycast={() => null}>
      {CAR_ARCS.map((arc, i) => {
        const a = 0.35 - arc / radius
        return (
          <group
            key={i}
            ref={(el) => {
              carRefs.current[i] = el
              if (i === 0) locoRef.current = el
            }}
            position={[Math.cos(a) * radius, y, Math.sin(a) * radius + Z_OFF]}
            rotation={[0, -a + Math.PI / 2, 0]}
          >
            <CarBody color={CAR_COLORS[i]} loco={i === 0} />
          </group>
        )
      })}
      <SmokeTrail locoRef={locoRef} />
    </group>
  )
}

/** Wooden sleepers + dual steel rails + fishplates — classic circular railroad. */
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

  const innerR = radius - RAIL_GAUGE / 2
  const outerR = radius + RAIL_GAUGE / 2

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.02, Z_OFF]}>
        <ringGeometry args={[radius - 0.9, radius + 0.9, SEGMENTS]} />
        <meshBasicMaterial color="#14101c" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.005, Z_OFF]}>
        <ringGeometry args={[radius - 0.68, radius + 0.68, SEGMENTS]} />
        <meshBasicMaterial color="#2a2234" />
      </mesh>

      {ties.map((t, i) => (
        <mesh key={i} position={[t.x, y + 0.035, t.z]} rotation={[0, t.rot, 0]}>
          <boxGeometry args={[1.2, 0.08, 0.2]} />
          <meshBasicMaterial color={i % 3 === 0 ? '#6a4422' : '#5a3a1e'} />
        </mesh>
      ))}

      {/* Dual rails */}
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.05, 6, SEGMENTS]} />
        <meshBasicMaterial color="#b8dce0" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.1, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.05, 6, SEGMENTS]} />
        <meshBasicMaterial color="#b8dce0" toneMapped={false} />
      </mesh>
      {/* Thin rail caps for a bit more read from high cam */}
      <mesh position={[0, y + 0.145, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[innerR, 0.022, 5, SEGMENTS]} />
        <meshBasicMaterial color="#e8f6f8" toneMapped={false} />
      </mesh>
      <mesh position={[0, y + 0.145, Z_OFF]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[outerR, 0.022, 5, SEGMENTS]} />
        <meshBasicMaterial color="#e8f6f8" toneMapped={false} />
      </mesh>

      {/* Fishplates / joint hardware */}
      {plates.map((p, i) => (
        <group key={`pl-${i}`} position={[p.x, y + 0.1, p.z]} rotation={[0, p.rot, 0]}>
          <mesh position={[0, 0, -RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.22, 0.06, 0.1]} />
            <meshBasicMaterial color="#6a7488" />
          </mesh>
          <mesh position={[0, 0, RAIL_GAUGE / 2]}>
            <boxGeometry args={[0.22, 0.06, 0.1]} />
            <meshBasicMaterial color="#6a7488" />
          </mesh>
        </group>
      ))}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.028, Z_OFF]}>
        <ringGeometry args={[innerR - 0.12, outerR + 0.12, 48]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.16} depthWrite={false} />
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
            <meshBasicMaterial
              color={i % 3 === 0 ? '#39ff14' : i % 3 === 1 ? '#f9c80e' : '#ff2a6d'}
              toneMapped={false}
            />
          </mesh>
        </group>
      ))}
    </group>
  )
}

export { RAIL_GAUGE }
