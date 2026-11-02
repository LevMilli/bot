import { useMemo } from 'react'
import { PlazaRailroad, PlazaTrain } from './PlazaTrain'
import {
  BACK_ROAD_HALF_LEN,
  BACK_ROAD_HALF_W,
  BACK_ROAD_Z,
  PLAZA_RAIL_R,
  RAIL_R,
  RAIL_Z_OFF,
} from './plazaLayout'

export { PLAZA_RAIL_R }

function PlazaRail({ radius = RAIL_R }: { radius?: number }) {
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
    </group>
  )
}

/**
 * Back-only avenue. Where it crosses the circular railroad, the deck rises on a bridge
 * so asphalt never sits on the rails. No road on the camera / vault front.
 */
function BackAvenueBridge() {
  const crossings = useMemo(() => {
    // Horizontal line z = BACK_ROAD_Z intersects circle (0, RAIL_Z_OFF) r=RAIL_R at ±x.
    const dz = BACK_ROAD_Z - RAIL_Z_OFF
    const disc = RAIL_R * RAIL_R - dz * dz
    if (disc <= 0) return [] as number[]
    const x = Math.sqrt(disc)
    return [-x, x]
  }, [])

  const bridgeHalf = 2.35
  const deckY = 1.28
  const roadY = 0.04

  // Split the road into flat segments that skip bridge spans.
  const flats = useMemo(() => {
    const xs = [-BACK_ROAD_HALF_LEN, ...crossings.flatMap((c) => [c - bridgeHalf, c + bridgeHalf]), BACK_ROAD_HALF_LEN]
    const segs: { cx: number; w: number }[] = []
    for (let i = 0; i < xs.length - 1; i += 2) {
      const a = xs[i]
      const b = xs[i + 1]
      if (b - a < 0.4) continue
      segs.push({ cx: (a + b) / 2, w: b - a })
    }
    return segs
  }, [crossings])

  return (
    <group>
      {/* curb glow — back side only */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, roadY + 0.01, BACK_ROAD_Z - BACK_ROAD_HALF_W - 0.12]}>
        <planeGeometry args={[BACK_ROAD_HALF_LEN * 2, 0.05]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.3} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, roadY + 0.01, BACK_ROAD_Z + BACK_ROAD_HALF_W + 0.12]}>
        <planeGeometry args={[BACK_ROAD_HALF_LEN * 2, 0.05]} />
        <meshBasicMaterial color="#ff2a6d" transparent opacity={0.22} />
      </mesh>

      {flats.map((s, i) => (
        <group key={i}>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[s.cx, roadY, BACK_ROAD_Z]}>
            <planeGeometry args={[s.w, BACK_ROAD_HALF_W * 2]} />
            <meshBasicMaterial color="#141820" />
          </mesh>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[s.cx, roadY + 0.008, BACK_ROAD_Z]}>
            <planeGeometry args={[s.w * 0.92, 0.06]} />
            <meshBasicMaterial color="#f9c80e" transparent opacity={0.45} />
          </mesh>
        </group>
      ))}

      {crossings.map((cx, i) => (
        <group key={`br-${i}`} position={[cx, 0, BACK_ROAD_Z]}>
          {/* piers outside the gauge */}
          {([-1.15, 1.15] as const).map((pz) =>
            ([-1.55, 1.55] as const).map((px) => (
              <mesh key={`${px}-${pz}`} position={[px, 0.55, pz]}>
                <boxGeometry args={[0.28, 1.1, 0.28]} />
                <meshBasicMaterial color="#2a2438" />
              </mesh>
            )),
          )}
          {/* deck */}
          <mesh position={[0, deckY, 0]}>
            <boxGeometry args={[bridgeHalf * 2, 0.16, BACK_ROAD_HALF_W * 2 + 0.35]} />
            <meshBasicMaterial color="#1a1e28" />
          </mesh>
          <mesh position={[0, deckY + 0.09, 0]}>
            <boxGeometry args={[bridgeHalf * 2 - 0.2, 0.04, 0.08]} />
            <meshBasicMaterial color="#f9c80e" toneMapped={false} />
          </mesh>
          {/* neon railings */}
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[0, deckY + 0.38, side * (BACK_ROAD_HALF_W + 0.05)]}>
              <boxGeometry args={[bridgeHalf * 2 - 0.1, 0.08, 0.06]} />
              <meshBasicMaterial color="#2de2e6" toneMapped={false} />
            </mesh>
          ))}
          {/* approach ramps */}
          {([-1, 1] as const).map((dir) => (
            <mesh
              key={`ramp-${dir}`}
              position={[dir * (bridgeHalf + 1.1), deckY * 0.45, 0]}
              rotation={[0, 0, dir * -0.42]}
            >
              <boxGeometry args={[2.4, 0.14, BACK_ROAD_HALF_W * 2]} />
              <meshBasicMaterial color="#181c26" />
            </mesh>
          ))}
        </group>
      ))}

      {/* a couple cars parked on the back avenue (not on bridges) */}
      <Car position={[-8.5, 0, BACK_ROAD_Z]} rotation={0} color="#ff2a6d" />
      <Car position={[7.2, 0, BACK_ROAD_Z]} rotation={Math.PI} color="#2de2e6" />
    </group>
  )
}

/** Parks / lamps / people — front stays clear of asphalt. */
function PlazaDressing() {
  const lamps = useMemo(
    () =>
      [
        [-11, 0, -6],
        [11, 0, -6],
        [0, 0, -16.5],
        [-14, 0, -11.2],
        [14, 0, -11.2],
        [-9, 0, 3],
        [9, 0, 3],
      ] as [number, number, number][],
    [],
  )

  const people = useMemo(
    () =>
      [
        { p: [2.2, 0, 3.2] as [number, number, number], h: '#2de2e6' },
        { p: [-3.1, 0, 2.8] as [number, number, number], h: '#ff2a6d' },
        { p: [6.4, 0, -8.2] as [number, number, number], h: '#f9c80e' },
        { p: [-7.0, 0, -3.2] as [number, number, number], h: '#b967ff' },
      ] as const,
    [],
  )

  return (
    <group>
      <BackAvenueBridge />

      <ParkBlock position={[-13.5, 0, 1.5]} size={[5.2, 4.2]} />
      <ParkBlock position={[13.8, 0, -4.5]} size={[5.0, 4.5]} />
      <ParkBlock position={[0, 0, -17.8]} size={[7, 3.2]} />

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
