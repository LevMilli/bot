import { useMemo } from 'react'
import { PlazaRailroad, PlazaTrain } from './PlazaTrain'

export const PLAZA_RAIL_R = 12.4

function PlazaRail({ radius = PLAZA_RAIL_R }: { radius?: number }) {
  return (
    <group>
      <PlazaRailroad radius={radius} y={0.06} />
      {/* Train rides the rail centerline just above the ties */}
      {/* y chosen so wheel bottoms sit on the rail torus */}
      <PlazaTrain radius={radius} y={0.2} />
    </group>
  )
}

function RadialSpokes({ count = 16, radius = 12 }: { count?: number; radius?: number }) {
  const spokes = useMemo(() => {
    const out: { position: [number, number, number]; rotation: [number, number, number]; length: number }[] = []
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2
      const inner = 1.2
      const length = radius - inner
      const mid = inner + length / 2
      out.push({
        position: [Math.cos(a) * mid, 0.03, Math.sin(a) * mid - 1],
        rotation: [0, -a, 0],
        length,
      })
    }
    return out
  }, [count, radius])

  return (
    <group>
      {spokes.map((s, i) => (
        <mesh key={i} position={s.position} rotation={s.rotation}>
          <boxGeometry args={[s.length, 0.01, 0.03]} />
          <meshBasicMaterial color="#1a9cff" transparent opacity={0.38} />
        </mesh>
      ))}
    </group>
  )
}

export function GridFloor({
  size = 90,
  cell = 1,
  plaza = true,
}: {
  size?: number
  cell?: number
  plaza?: boolean
}) {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <planeGeometry args={[size, size]} />
        <meshStandardMaterial color="#020018" roughness={0.92} metalness={0.08} />
      </mesh>
      {/* Bright cyan synthwave grid */}
      <gridHelper args={[size, Math.floor(size / cell), '#2de2e6', '#0a3cff']} position={[0, 0.01, 0]} />
      <gridHelper
        args={[size, Math.floor(size / (cell * 5)), '#7ef9ff', '#0a2060']}
        position={[0, 0.02, 0]}
      />
      {plaza && (
        <>
          <RadialSpokes />
          <PlazaRail />
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.035, -1]}>
            <ringGeometry args={[4.2, 4.45, 64]} />
            <meshBasicMaterial color="#2de2e6" transparent opacity={0.4} />
          </mesh>
          {/* Inner radar rings */}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.038, -1]}>
            <ringGeometry args={[6.8, 6.95, 64]} />
            <meshBasicMaterial color="#7ef9ff" transparent opacity={0.28} />
          </mesh>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.04, -1]}>
            <ringGeometry args={[9.6, 9.75, 96]} />
            <meshBasicMaterial color="#2de2e6" transparent opacity={0.22} />
          </mesh>
        </>
      )}
    </group>
  )
}
