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

/** Visual lamp only — no real lights. */
function StreetLamp({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.55, 0]}>
        <cylinderGeometry args={[0.04, 0.05, 1.1, 5]} />
        <meshBasicMaterial color="#1a1e28" />
      </mesh>
      <mesh position={[0, 1.08, 0.1]}>
        <sphereGeometry args={[0.08, 6, 6]} />
        <meshBasicMaterial color="#ffe9a0" toneMapped={false} />
      </mesh>
    </group>
  )
}

function Pedestrian({ position, hue }: { position: [number, number, number]; hue: string }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.28, 0]}>
        <cylinderGeometry args={[0.07, 0.08, 0.36, 5]} />
        <meshBasicMaterial color={hue} />
      </mesh>
      <mesh position={[0, 0.55, 0]}>
        <sphereGeometry args={[0.08, 6, 6]} />
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
            <sphereGeometry args={[0.28, 6, 6]} />
            <meshBasicMaterial color="#2a6b38" />
          </mesh>
        </group>
      ))}
    </group>
  )
}

/** Plaza dressing without roads — parks, lamps, people + railroad. */
function PlazaDressing() {
  const lamps = useMemo(
    () =>
      [
        [-10, 0, 8],
        [10, 0, 8],
        [-11, 0, -6],
        [11, 0, -6],
        [0, 0, -13],
        [-6, 0, 9.5],
        [6, 0, 9.5],
      ] as [number, number, number][],
    [],
  )

  const people = useMemo(
    () =>
      [
        { p: [2.2, 0, 7.2] as [number, number, number], h: '#2de2e6' },
        { p: [-3.1, 0, 7.6] as [number, number, number], h: '#ff2a6d' },
        { p: [6.4, 0, -8.2] as [number, number, number], h: '#f9c80e' },
        { p: [-7.0, 0, -3.2] as [number, number, number], h: '#b967ff' },
      ] as const,
    [],
  )

  return (
    <group>
      {/* Soft neon plaza rim — no asphalt avenues */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 7.4]}>
        <planeGeometry args={[28, 0.05]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.28} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 9.0]}>
        <planeGeometry args={[28, 0.05]} />
        <meshBasicMaterial color="#ff2a6d" transparent opacity={0.2} />
      </mesh>

      <ParkBlock position={[-12.5, 0, 2.5]} size={[5.5, 4.5]} />
      <ParkBlock position={[12.8, 0, -5.5]} size={[5.2, 5.0]} />

      {lamps.map((p, i) => (
        <StreetLamp key={i} position={p} />
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
      {/* night ground — no purple grid, no roads */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
        <planeGeometry args={[size, size]} />
        <meshBasicMaterial color="#0a0c14" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, -2]}>
        <planeGeometry args={[36, 36]} />
        <meshBasicMaterial color="#12151e" />
      </mesh>
      {plaza && (
        <>
          <PlazaDressing />
          <PlazaRail />
        </>
      )}
    </group>
  )
}
