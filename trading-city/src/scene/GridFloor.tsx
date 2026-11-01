import { useMemo } from 'react'
import { PlazaRailroad, PlazaTrain } from './PlazaTrain'

export const PLAZA_RAIL_R = 12.4

function PlazaRail({ radius = PLAZA_RAIL_R }: { radius?: number }) {
  return (
    <group>
      <PlazaRailroad radius={radius} y={0.06} />
      <PlazaTrain radius={radius} y={0.2} />
    </group>
  )
}

function StreetLamp({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.55, 0]}>
        <cylinderGeometry args={[0.04, 0.05, 1.1, 8]} />
        <meshStandardMaterial color="#1a1e28" metalness={0.55} roughness={0.4} />
      </mesh>
      <mesh position={[0, 1.15, 0.12]} rotation={[0.4, 0, 0]}>
        <boxGeometry args={[0.04, 0.04, 0.28]} />
        <meshStandardMaterial color="#1a1e28" metalness={0.55} roughness={0.4} />
      </mesh>
      <mesh position={[0, 1.08, 0.28]}>
        <sphereGeometry args={[0.07, 10, 10]} />
        <meshBasicMaterial color="#ffe9a0" toneMapped={false} />
      </mesh>
      <pointLight position={[0, 1.08, 0.28]} intensity={0.55} distance={4.5} color="#ffe9a0" />
    </group>
  )
}

function Car({
  position,
  rotation = 0,
  color,
}: {
  position: [number, number, number]
  rotation?: number
  color: string
}) {
  return (
    <group position={position} rotation={[0, rotation, 0]}>
      <mesh position={[0, 0.18, 0]} castShadow>
        <boxGeometry args={[0.85, 0.28, 0.42]} />
        <meshStandardMaterial color={color} metalness={0.35} roughness={0.4} emissive={color} emissiveIntensity={0.12} />
      </mesh>
      <mesh position={[0.05, 0.36, 0]}>
        <boxGeometry args={[0.45, 0.2, 0.38]} />
        <meshStandardMaterial color="#0e1218" metalness={0.3} roughness={0.5} />
      </mesh>
      {([-0.28, 0.28] as const).map((z) =>
        ([-0.28, 0.28] as const).map((x) => (
          <mesh key={`${x}-${z}`} position={[x, 0.08, z]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.08, 0.08, 0.06, 10]} />
            <meshStandardMaterial color="#111" metalness={0.6} roughness={0.4} />
          </mesh>
        )),
      )}
    </group>
  )
}

function Pedestrian({ position, hue }: { position: [number, number, number]; hue: string }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.28, 0]}>
        <cylinderGeometry args={[0.07, 0.08, 0.36, 8]} />
        <meshStandardMaterial color={hue} roughness={0.7} />
      </mesh>
      <mesh position={[0, 0.55, 0]}>
        <sphereGeometry args={[0.08, 10, 10]} />
        <meshStandardMaterial color="#e8d4b8" roughness={0.65} />
      </mesh>
    </group>
  )
}

function ParkBlock({ position, size }: { position: [number, number, number]; size: [number, number] }) {
  const [w, d] = size
  return (
    <group position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]} receiveShadow>
        <planeGeometry args={[w, d]} />
        <meshStandardMaterial color="#14301c" roughness={0.95} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.025, 0]}>
        <planeGeometry args={[w * 0.72, d * 0.72]} />
        <meshStandardMaterial color="#1f4a28" roughness={0.9} />
      </mesh>
      {/* simple trees */}
      {[
        [-w * 0.25, d * 0.2],
        [w * 0.2, -d * 0.15],
        [0, d * 0.05],
      ].map(([x, z], i) => (
        <group key={i} position={[x, 0, z]}>
          <mesh position={[0, 0.25, 0]}>
            <cylinderGeometry args={[0.05, 0.07, 0.5, 6]} />
            <meshStandardMaterial color="#3a2418" />
          </mesh>
          <mesh position={[0, 0.65, 0]}>
            <sphereGeometry args={[0.28, 10, 10]} />
            <meshStandardMaterial color="#2a6b38" emissive="#1a4020" emissiveIntensity={0.15} />
          </mesh>
        </group>
      ))}
      {/* park bench */}
      <mesh position={[0, 0.18, d * 0.28]}>
        <boxGeometry args={[0.55, 0.06, 0.18]} />
        <meshStandardMaterial color="#2a2430" />
      </mesh>
    </group>
  )
}

/** Neon-NYC plaza floor — asphalt streets, sidewalks, parks, lamps, cars, people. */
function NycStreets() {
  const lamps = useMemo(() => {
    const out: [number, number, number][] = []
    for (let i = -4; i <= 4; i++) {
      out.push([i * 4.5, 0, 10.5])
      out.push([i * 4.5, 0, -12.5])
      out.push([14.5, 0, i * 3.5 - 1])
      out.push([-14.5, 0, i * 3.5 - 1])
    }
    return out
  }, [])

  const cars = useMemo(
    () =>
      [
        { p: [3.2, 0, 8.2] as [number, number, number], r: 0, c: '#ff2a6d' },
        { p: [-5.5, 0, 8.0] as [number, number, number], r: Math.PI, c: '#2de2e6' },
        { p: [8.5, 0, -2.5] as [number, number, number], r: Math.PI / 2, c: '#f9c80e' },
        { p: [-8.2, 0, 1.5] as [number, number, number], r: -Math.PI / 2, c: '#b967ff' },
        { p: [1.2, 0, -10.5] as [number, number, number], r: 0.2, c: '#39ff14' },
        { p: [11.5, 0, 4.0] as [number, number, number], r: Math.PI / 2, c: '#ff6b35' },
      ] as const,
    [],
  )

  const people = useMemo(
    () =>
      [
        { p: [2.2, 0, 6.4] as [number, number, number], h: '#2de2e6' },
        { p: [-3.1, 0, 6.8] as [number, number, number], h: '#ff2a6d' },
        { p: [6.4, 0, 2.1] as [number, number, number], h: '#f9c80e' },
        { p: [-7.0, 0, -3.2] as [number, number, number], h: '#b967ff' },
        { p: [4.8, 0, -7.5] as [number, number, number], h: '#39ff14' },
        { p: [-2.4, 0, 9.2] as [number, number, number], h: '#7ef9ff' },
        { p: [9.1, 0, -0.5] as [number, number, number], h: '#e8d4b8' },
        { p: [-10.2, 0, 3.4] as [number, number, number], h: '#2de2e6' },
      ] as const,
    [],
  )

  return (
    <group>
      {/* asphalt avenue E–W (toward camera / vault side) */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, 8.2]} receiveShadow>
        <planeGeometry args={[48, 2.4]} />
        <meshStandardMaterial color="#141820" roughness={0.92} />
      </mesh>
      {/* center dashed line */}
      {Array.from({ length: 16 }).map((_, i) => (
        <mesh key={`ew-${i}`} rotation={[-Math.PI / 2, 0, 0]} position={[(i - 7.5) * 2.8, 0.012, 8.2]}>
          <planeGeometry args={[1.1, 0.08]} />
          <meshBasicMaterial color="#f9c80e" transparent opacity={0.55} />
        </mesh>
      ))}

      {/* asphalt avenue N–S */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[8.8, 0.005, -1]} receiveShadow>
        <planeGeometry args={[2.4, 42]} />
        <meshStandardMaterial color="#141820" roughness={0.92} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-8.8, 0.005, -1]} receiveShadow>
        <planeGeometry args={[2.4, 42]} />
        <meshStandardMaterial color="#141820" roughness={0.92} />
      </mesh>
      {Array.from({ length: 14 }).map((_, i) => (
        <mesh key={`ns-${i}`} rotation={[-Math.PI / 2, 0, 0]} position={[8.8, 0.012, (i - 6.5) * 2.6 - 1]}>
          <planeGeometry args={[0.08, 1.1]} />
          <meshBasicMaterial color="#f9c80e" transparent opacity={0.5} />
        </mesh>
      ))}

      {/* cross street behind plaza */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, -11.2]} receiveShadow>
        <planeGeometry args={[48, 2.2]} />
        <meshStandardMaterial color="#141820" roughness={0.92} />
      </mesh>

      {/* sidewalks */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, 6.6]} receiveShadow>
        <planeGeometry args={[40, 0.85]} />
        <meshStandardMaterial color="#2a2436" roughness={0.88} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, 9.8]} receiveShadow>
        <planeGeometry args={[40, 0.85]} />
        <meshStandardMaterial color="#2a2436" roughness={0.88} />
      </mesh>

      {/* neon curb glow (keeps SIGNAL-CITY vibe without purple grid squares) */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.014, 7.05]}>
        <planeGeometry args={[40, 0.06]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.35} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.014, 9.35]}>
        <planeGeometry args={[40, 0.06]} />
        <meshBasicMaterial color="#ff2a6d" transparent opacity={0.28} />
      </mesh>

      <ParkBlock position={[-12.5, 0, 2.5]} size={[5.5, 4.5]} />
      <ParkBlock position={[12.8, 0, -5.5]} size={[5.2, 5.0]} />
      <ParkBlock position={[-4.5, 0, -14.5]} size={[6.5, 3.8]} />

      {lamps.map((p, i) => (
        <StreetLamp key={i} position={p} />
      ))}
      {cars.map((c, i) => (
        <Car key={i} position={c.p} rotation={c.r} color={c.c} />
      ))}
      {people.map((p, i) => (
        <Pedestrian key={i} position={p.p} hue={p.h} />
      ))}
    </group>
  )
}

export function GridFloor({
  size = 90,
  plaza = true,
}: {
  size?: number
  cell?: number
  plaza?: boolean
}) {
  return (
    <group>
      {/* base asphalt / night ground — no purple grid squares */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <planeGeometry args={[size, size]} />
        <meshStandardMaterial color="#0a0c14" roughness={0.95} metalness={0.05} />
      </mesh>
      {/* soft city block tint */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, -2]} receiveShadow>
        <planeGeometry args={[36, 36]} />
        <meshStandardMaterial color="#12151e" roughness={0.92} />
      </mesh>
      {plaza && (
        <>
          <NycStreets />
          <PlazaRail />
        </>
      )}
    </group>
  )
}
