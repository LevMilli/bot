import { useMemo } from 'react'
import { PlazaTrain, RailPosts } from './PlazaTrain'

export const PLAZA_RAIL_R = 12.4

function PlazaRail({ radius = PLAZA_RAIL_R, y = 0.28 }: { radius?: number; y?: number }) {
  const lights = useMemo(() => {
    const pts: [number, number, number][] = []
    const n = 48
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2
      pts.push([Math.cos(a) * radius, y + 0.08, Math.sin(a) * radius - 1])
    }
    return pts
  }, [radius, y])

  return (
    <group>
      {/* Track bed */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, y - 0.06, -1]}>
        <ringGeometry args={[radius - 0.28, radius + 0.28, 128]} />
        <meshStandardMaterial color="#060a16" metalness={0.35} roughness={0.55} />
      </mesh>
      {/* Double elevated rail */}
      <mesh position={[0, y, -1]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius, 0.04, 10, 128]} />
        <meshBasicMaterial color="#7ef9ff" transparent opacity={0.95} />
      </mesh>
      <mesh position={[0, y + 0.22, -1]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius, 0.032, 10, 128]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.9} />
      </mesh>
      <mesh position={[0, y + 0.11, -1]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius - 0.1, 0.014, 8, 128]} />
        <meshBasicMaterial color="#c8f7ff" transparent opacity={0.5} />
      </mesh>
      {/* Outer guide rail */}
      <mesh position={[0, y + 0.12, -1]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius + 0.22, 0.018, 8, 128]} />
        <meshBasicMaterial color="#b967ff" transparent opacity={0.55} />
      </mesh>
      {/* Soft ground projection of the rail */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, -1]}>
        <ringGeometry args={[radius - 0.12, radius + 0.18, 96]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.22} depthWrite={false} />
      </mesh>
      <RailPosts radius={radius} y={y} />
      {lights.map((p, i) => (
        <mesh key={i} position={p} raycast={() => null}>
          <sphereGeometry args={[0.07, 10, 10]} />
          <meshBasicMaterial color={i % 3 === 0 ? '#ffffff' : '#7ef9ff'} />
        </mesh>
      ))}
      <PlazaTrain radius={radius} y={y + 0.14} />
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
