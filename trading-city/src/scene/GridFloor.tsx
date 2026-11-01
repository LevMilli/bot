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

/** Visual lamp only — no per-lamp pointLights (those tanked the city frame rate). */
function StreetLamp({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.55, 0]}>
        <cylinderGeometry args={[0.04, 0.05, 1.1, 6]} />
        <meshBasicMaterial color="#1a1e28" />
      </mesh>
      <mesh position={[0, 1.15, 0.12]} rotation={[0.4, 0, 0]}>
        <boxGeometry args={[0.04, 0.04, 0.28]} />
        <meshBasicMaterial color="#1a1e28" />
      </mesh>
      <mesh position={[0, 1.08, 0.28]}>
        <sphereGeometry args={[0.08, 8, 8]} />
        <meshBasicMaterial color="#ffe9a0" toneMapped={false} />
      </mesh>
      {/* Cheap glow disc — reads like light spill without a real light */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0.05]}>
        <circleGeometry args={[0.55, 10]} />
        <meshBasicMaterial color="#ffe9a0" transparent opacity={0.12} depthWrite={false} />
      </mesh>
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
      <mesh position={[0, 0.18, 0]}>
        <boxGeometry args={[0.85, 0.28, 0.42]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <mesh position={[0.05, 0.36, 0]}>
        <boxGeometry args={[0.45, 0.2, 0.38]} />
        <meshBasicMaterial color="#0e1218" />
      </mesh>
      {([-0.28, 0.28] as const).map((z) =>
        ([-0.28, 0.28] as const).map((x) => (
          <mesh key={`${x}-${z}`} position={[x, 0.08, z]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.08, 0.08, 0.06, 8]} />
            <meshBasicMaterial color="#111" />
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
        <cylinderGeometry args={[0.07, 0.08, 0.36, 6]} />
        <meshBasicMaterial color={hue} />
      </mesh>
      <mesh position={[0, 0.55, 0]}>
        <sphereGeometry args={[0.08, 8, 8]} />
        <meshBasicMaterial color="#e8d4b8" />
      </mesh>
    </group>
  )
}

function ParkBlock({ position, size }: { position: [number, number, number]; size: [number, number] }) {
  const [w, d] = size
  return (
    <group position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <planeGeometry args={[w, d]} />
        <meshBasicMaterial color="#14301c" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.025, 0]}>
        <planeGeometry args={[w * 0.72, d * 0.72]} />
        <meshBasicMaterial color="#1f4a28" />
      </mesh>
      {[
        [-w * 0.25, d * 0.2],
        [w * 0.2, -d * 0.15],
      ].map(([x, z], i) => (
        <group key={i} position={[x, 0, z]}>
          <mesh position={[0, 0.25, 0]}>
            <cylinderGeometry args={[0.05, 0.07, 0.5, 5]} />
            <meshBasicMaterial color="#3a2418" />
          </mesh>
          <mesh position={[0, 0.65, 0]}>
            <sphereGeometry args={[0.28, 8, 8]} />
            <meshBasicMaterial color="#2a6b38" />
          </mesh>
        </group>
      ))}
      <mesh position={[0, 0.18, d * 0.28]}>
        <boxGeometry args={[0.55, 0.06, 0.18]} />
        <meshBasicMaterial color="#2a2430" />
      </mesh>
    </group>
  )
}

/** Neon-NYC plaza floor — asphalt streets, sidewalks, parks, lamps, cars, people. */
function NycStreets() {
  // Sparse lamp row — glow is fake; city lights handle real illumination.
  const lamps = useMemo(
    () =>
      [
        [-9, 0, 10.5],
        [-3, 0, 10.5],
        [3, 0, 10.5],
        [9, 0, 10.5],
        [-9, 0, -12.5],
        [0, 0, -12.5],
        [9, 0, -12.5],
        [14.5, 0, -4],
        [14.5, 0, 4],
        [-14.5, 0, -4],
        [-14.5, 0, 4],
        [0, 0, 6.6],
      ] as [number, number, number][],
    [],
  )

  const cars = useMemo(
    () =>
      [
        { p: [3.2, 0, 8.2] as [number, number, number], r: 0, c: '#ff2a6d' },
        { p: [-5.5, 0, 8.0] as [number, number, number], r: Math.PI, c: '#2de2e6' },
        { p: [8.5, 0, -2.5] as [number, number, number], r: Math.PI / 2, c: '#f9c80e' },
        { p: [-8.2, 0, 1.5] as [number, number, number], r: -Math.PI / 2, c: '#b967ff' },
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
      ] as const,
    [],
  )

  // One dashed strip per avenue instead of dozens of tiny planes.
  const dashMat = useMemo(
    () => ({ color: '#f9c80e', transparent: true, opacity: 0.45 } as const),
    [],
  )

  return (
    <group>
      {/* asphalt avenue E–W (toward camera / vault side) */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, 8.2]}>
        <planeGeometry args={[48, 2.4]} />
        <meshBasicMaterial color="#141820" />
      </mesh>
      {/* center line as a thin continuous stripe (cheaper than 16 dash meshes) */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 8.2]}>
        <planeGeometry args={[44, 0.06]} />
        <meshBasicMaterial {...dashMat} />
      </mesh>

      {/* asphalt avenues N–S */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[8.8, 0.005, -1]}>
        <planeGeometry args={[2.4, 42]} />
        <meshBasicMaterial color="#141820" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-8.8, 0.005, -1]}>
        <planeGeometry args={[2.4, 42]} />
        <meshBasicMaterial color="#141820" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[8.8, 0.012, -1]}>
        <planeGeometry args={[0.06, 38]} />
        <meshBasicMaterial {...dashMat} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-8.8, 0.012, -1]}>
        <planeGeometry args={[0.06, 38]} />
        <meshBasicMaterial {...dashMat} />
      </mesh>

      {/* cross street behind plaza */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, -11.2]}>
        <planeGeometry args={[48, 2.2]} />
        <meshBasicMaterial color="#141820" />
      </mesh>

      {/* sidewalks */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, 6.6]}>
        <planeGeometry args={[40, 0.85]} />
        <meshBasicMaterial color="#2a2436" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, 9.8]}>
        <planeGeometry args={[40, 0.85]} />
        <meshBasicMaterial color="#2a2436" />
      </mesh>

      {/* neon curb glow */}
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
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
        <planeGeometry args={[size, size]} />
        <meshBasicMaterial color="#0a0c14" />
      </mesh>
      {/* soft city block tint */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, -2]}>
        <planeGeometry args={[36, 36]} />
        <meshBasicMaterial color="#12151e" />
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
