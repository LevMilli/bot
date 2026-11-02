import { useMemo } from 'react'
import * as THREE from 'three'
import { PlazaRailroad, PlazaTrain } from './PlazaTrain'
import {
  BACK_ROAD_HALF_LEN,
  BACK_ROAD_HALF_W,
  BACK_ROAD_Z,
  PLAZA_RAIL_R,
  RAIL_CLEAR,
  RAIL_R,
  distFromRailCenter,
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
        [-w * 0.28, d * 0.22],
        [w * 0.22, -d * 0.18],
        [0, d * 0.05],
      ].map(([x, z], i) => (
        <group key={i} position={[x, 0, z]}>
          <mesh position={[0, 0.22, 0]}>
            <cylinderGeometry args={[0.045, 0.06, 0.44, 5]} />
            <meshBasicMaterial color="#3a2418" />
          </mesh>
          <mesh position={[0, 0.58, 0]}>
            <sphereGeometry args={[0.24, 6, 6]} />
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

/** Cheap city-block / park tint baked into one canvas texture (no mesh spam). */
function usePlazaGroundTexture() {
  return useMemo(() => {
    const size = 512
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#0a0c14'
    ctx.fillRect(0, 0, size, size)

    // Soft plaza disc
    const g = ctx.createRadialGradient(size * 0.5, size * 0.48, 20, size * 0.5, size * 0.48, size * 0.42)
    g.addColorStop(0, '#161a24')
    g.addColorStop(0.55, '#10141c')
    g.addColorStop(1, '#0a0c14')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)

    // City block grid (subtle)
    ctx.strokeStyle = 'rgba(45, 226, 230, 0.07)'
    ctx.lineWidth = 1
    const step = 28
    for (let i = 0; i <= size; i += step) {
      ctx.beginPath()
      ctx.moveTo(i, 0)
      ctx.lineTo(i, size)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(0, i)
      ctx.lineTo(size, i)
      ctx.stroke()
    }

    // Park patches scattered across the map
    const parks: [number, number, number, number, string][] = [
      [0.12, 0.22, 0.14, 0.1, '#14301c'],
      [0.78, 0.18, 0.12, 0.11, '#163820'],
      [0.18, 0.55, 0.11, 0.09, '#14301c'],
      [0.82, 0.58, 0.13, 0.1, '#1a3c24'],
      [0.48, 0.12, 0.16, 0.08, '#14301c'],
      [0.55, 0.78, 0.18, 0.1, '#163820'],
      [0.28, 0.82, 0.12, 0.09, '#14301c'],
      [0.72, 0.82, 0.11, 0.08, '#1a3c24'],
      [0.08, 0.72, 0.1, 0.08, '#14301c'],
      [0.9, 0.4, 0.09, 0.1, '#163820'],
      [0.38, 0.4, 0.1, 0.08, '#14301c'],
      [0.62, 0.45, 0.09, 0.07, '#1a3c24'],
    ]
    for (const [u, v, w, h, c] of parks) {
      ctx.fillStyle = c
      ctx.fillRect(u * size, v * size, w * size, h * size)
      ctx.fillStyle = '#1f4a28'
      ctx.fillRect(u * size + 4, v * size + 4, w * size * 0.7, h * size * 0.7)
    }

    // Neon curb rings hint
    ctx.strokeStyle = 'rgba(255, 42, 109, 0.12)'
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.arc(size * 0.5, size * 0.48, size * 0.28, 0, Math.PI * 2)
    ctx.stroke()
    ctx.strokeStyle = 'rgba(45, 226, 230, 0.1)'
    ctx.beginPath()
    ctx.arc(size * 0.5, size * 0.48, size * 0.34, 0, Math.PI * 2)
    ctx.stroke()

    const tex = new THREE.CanvasTexture(canvas)
    tex.colorSpace = THREE.SRGBColorSpace
    tex.anisotropy = 4
    tex.needsUpdate = true
    return tex
  }, [])
}

/**
 * Continuous elevated back avenue. One full deck spanning the plaza rear;
 * piers only where they clear the railroad (never on ballast/rails).
 */
function BackAvenueBridge() {
  const deckY = 1.35
  const deckLen = BACK_ROAD_HALF_LEN * 2
  const deckW = BACK_ROAD_HALF_W * 2 + 0.25
  const rampLen = 4.2

  const piers = useMemo(() => {
    const out: [number, number][] = []
    // Sample pier slots along the deck; keep only those clear of the rail band.
    for (let x = -BACK_ROAD_HALF_LEN + 1.2; x <= BACK_ROAD_HALF_LEN - 1.2; x += 2.4) {
      for (const zSide of [-0.95, 0.95] as const) {
        const wx = x
        const wz = BACK_ROAD_Z + zSide
        const gap = Math.abs(distFromRailCenter(wx, wz) - RAIL_R)
        if (gap < RAIL_CLEAR + 0.55) continue
        out.push([wx, zSide])
      }
    }
    return out
  }, [])

  return (
    <group>
      {/* continuous deck */}
      <mesh position={[0, deckY, BACK_ROAD_Z]}>
        <boxGeometry args={[deckLen, 0.18, deckW]} />
        <meshBasicMaterial color="#1a1e28" />
      </mesh>
      {/* center dashed stripe */}
      <mesh position={[0, deckY + 0.1, BACK_ROAD_Z]}>
        <boxGeometry args={[deckLen - 1.5, 0.04, 0.08]} />
        <meshBasicMaterial color="#f9c80e" toneMapped={false} />
      </mesh>
      {/* neon curb rails along full length */}
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[0, deckY + 0.42, BACK_ROAD_Z + side * (BACK_ROAD_HALF_W + 0.02)]}>
          <boxGeometry args={[deckLen - 0.4, 0.08, 0.06]} />
          <meshBasicMaterial color={side < 0 ? '#2de2e6' : '#ff2a6d'} toneMapped={false} />
        </mesh>
      ))}

      {/* end ramps down to grade — complete approaches */}
      {([-1, 1] as const).map((dir) => (
        <group key={`ramp-${dir}`} position={[dir * (BACK_ROAD_HALF_LEN + rampLen * 0.35), 0, BACK_ROAD_Z]}>
          <mesh position={[0, deckY * 0.5, 0]} rotation={[0, 0, dir * -0.32]}>
            <boxGeometry args={[rampLen, 0.16, deckW]} />
            <meshBasicMaterial color="#181c26" />
          </mesh>
          <mesh position={[dir * (rampLen * 0.55), 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[2.2, deckW]} />
            <meshBasicMaterial color="#141820" />
          </mesh>
        </group>
      ))}

      {/* piers clear of tracks */}
      {piers.map(([x, zSide], i) => (
        <mesh key={i} position={[x, deckY * 0.5, BACK_ROAD_Z + zSide]}>
          <boxGeometry args={[0.32, deckY - 0.08, 0.32]} />
          <meshBasicMaterial color="#2a2438" />
        </mesh>
      ))}

      <Car position={[-10.5, deckY, BACK_ROAD_Z]} rotation={0} color="#ff2a6d" />
      <Car position={[9.2, deckY, BACK_ROAD_Z]} rotation={Math.PI} color="#2de2e6" />
      <Car position={[0.8, deckY, BACK_ROAD_Z]} rotation={0} color="#f9c80e" />
    </group>
  )
}

function PlazaDressing() {
  const lamps = useMemo(
    () =>
      [
        [-11, 0, -6],
        [11, 0, -6],
        [0, 0, -16.8],
        [-16, 0, -11.2],
        [16, 0, -11.2],
        [-9, 0, 3],
        [9, 0, 3],
        [-14, 0, 8],
        [14, 0, 8],
        [0, 0, 10],
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
        { p: [4.0, 0, -15.5] as [number, number, number], h: '#39ff14' },
        { p: [-5.5, 0, -15.2] as [number, number, number], h: '#7ef9ff' },
      ] as const,
    [],
  )

  const parks = useMemo(
    () =>
      [
        { p: [-13.5, 0, 1.5] as [number, number, number], s: [5.2, 4.2] as [number, number] },
        { p: [13.8, 0, -4.5] as [number, number, number], s: [5.0, 4.5] as [number, number] },
        { p: [0, 0, -18.2] as [number, number, number], s: [8, 3.4] as [number, number] },
        { p: [-16, 0, -16] as [number, number, number], s: [4.5, 3.8] as [number, number] },
        { p: [16, 0, -16] as [number, number, number], s: [4.5, 3.8] as [number, number] },
        { p: [-15, 0, 8] as [number, number, number], s: [4.2, 3.5] as [number, number] },
        { p: [15, 0, 8] as [number, number, number], s: [4.2, 3.5] as [number, number] },
        { p: [0, 0, 12.5] as [number, number, number], s: [6, 3.2] as [number, number] },
      ] as const,
    [],
  )

  return (
    <group>
      <BackAvenueBridge />
      {parks.map((pk, i) => (
        <ParkBlock key={i} position={pk.p} size={pk.s} />
      ))}
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
  const groundTex = usePlazaGroundTexture()
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
        <planeGeometry args={[size, size]} />
        <meshBasicMaterial map={groundTex} />
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
