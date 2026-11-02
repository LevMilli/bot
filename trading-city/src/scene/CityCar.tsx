import { useMemo } from 'react'
import * as THREE from 'three'
import type { BotPose } from '../data/botPose'
import { BotFigure } from './BotFigure'

export type CarOccupancy = 'empty' | 'driver' | 'couple' | 'family'

type Props = {
  position: [number, number, number]
  /** Yaw in radians — forward is local −X (matches plaza train convention). */
  rotation?: number
  /** Body paint */
  color?: string
  /** Accent for trim / underglow */
  accent?: string
  occupancy?: CarOccupancy
  /** Real spotLight on the road — keep few of these for FPS. */
  castHeadlight?: boolean
  /** Slight idle wheel turn for parked cars */
  wheelYaw?: number
}

const POSES: BotPose[] = ['waiting', 'researching', 'trading', 'winning']

/**
 * Reusable SIGNAL-CITY street car (procedural R3F “model”).
 * Copy this component into other scenes for the same neon sedan language:
 * wheels, cabin glass, lit headlights, optional bot passengers.
 */
export function CityCar({
  position,
  rotation = 0,
  color = '#2de2e6',
  accent = '#7ef9ff',
  occupancy = 'driver',
  castHeadlight = false,
  wheelYaw = 0,
}: Props) {
  const passengers = useMemo(() => {
    if (occupancy === 'empty') return [] as { seat: [number, number, number]; pose: BotPose }[]
    if (occupancy === 'driver')
      return [{ seat: [0.06, 0.22, 0.1] as [number, number, number], pose: POSES[0] }]
    if (occupancy === 'couple')
      return [
        { seat: [0.06, 0.22, 0.1] as [number, number, number], pose: POSES[1] },
        { seat: [0.06, 0.22, -0.1] as [number, number, number], pose: POSES[2] },
      ]
    return [
      { seat: [0.08, 0.22, 0.1] as [number, number, number], pose: POSES[0] },
      { seat: [0.08, 0.22, -0.1] as [number, number, number], pose: POSES[3] },
      { seat: [-0.22, 0.2, 0] as [number, number, number], pose: POSES[1] },
    ]
  }, [occupancy])

  return (
    <group position={position} rotation={[0, rotation, 0]}>
      {/* underglow — blends car into neon plaza */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <planeGeometry args={[1.35, 0.7]} />
        <meshBasicMaterial color={accent} transparent opacity={0.14} depthWrite={false} />
      </mesh>

      {/* chassis */}
      <mesh position={[0, 0.2, 0]}>
        <boxGeometry args={[1.35, 0.22, 0.62]} />
        <meshStandardMaterial color={color} metalness={0.55} roughness={0.32} emissive={color} emissiveIntensity={0.12} />
      </mesh>
      {/* lower skirt */}
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={[1.38, 0.08, 0.64]} />
        <meshBasicMaterial color="#0a0e16" />
      </mesh>
      {/* hood taper */}
      <mesh position={[-0.42, 0.28, 0]}>
        <boxGeometry args={[0.42, 0.1, 0.58]} />
        <meshStandardMaterial color={color} metalness={0.5} roughness={0.35} />
      </mesh>
      {/* cabin */}
      <mesh position={[0.08, 0.42, 0]}>
        <boxGeometry args={[0.62, 0.28, 0.56]} />
        <meshBasicMaterial color="#0c1018" />
      </mesh>
      {/* windshield */}
      <mesh position={[-0.22, 0.42, 0]} rotation={[0, 0, -0.35]}>
        <boxGeometry args={[0.28, 0.22, 0.54]} />
        <meshBasicMaterial color="#9ee9ff" transparent opacity={0.35} depthWrite={false} toneMapped={false} />
      </mesh>
      {/* rear glass */}
      <mesh position={[0.38, 0.42, 0]} rotation={[0, 0, 0.28]}>
        <boxGeometry args={[0.22, 0.2, 0.54]} />
        <meshBasicMaterial color="#7ec8e0" transparent opacity={0.28} depthWrite={false} />
      </mesh>
      {/* side windows */}
      {([-1, 1] as const).map((side) => (
        <mesh key={side} position={[0.06, 0.44, side * 0.29]}>
          <boxGeometry args={[0.48, 0.16, 0.03]} />
          <meshBasicMaterial color="#b8f0ff" transparent opacity={0.4} depthWrite={false} toneMapped={false} />
        </mesh>
      ))}

      {/* bumper front / rear */}
      <mesh position={[-0.7, 0.16, 0]}>
        <boxGeometry args={[0.08, 0.12, 0.66]} />
        <meshBasicMaterial color="#1a2030" />
      </mesh>
      <mesh position={[0.7, 0.16, 0]}>
        <boxGeometry args={[0.08, 0.12, 0.66]} />
        <meshBasicMaterial color="#1a2030" />
      </mesh>

      {/* grille */}
      <mesh position={[-0.72, 0.22, 0]}>
        <boxGeometry args={[0.04, 0.1, 0.28]} />
        <meshBasicMaterial color="#0e1218" />
      </mesh>

      {/* headlights — emissive lenses */}
      {([-1, 1] as const).map((side) => (
        <group key={`hl-${side}`} position={[-0.7, 0.24, side * 0.22]}>
          <mesh>
            <boxGeometry args={[0.06, 0.08, 0.12]} />
            <meshBasicMaterial color="#fff6c8" toneMapped={false} />
          </mesh>
          {/* light cone on the road (fake volume — cheap) */}
          <mesh position={[-0.55, -0.12, 0]} rotation={[0, 0, -0.15]}>
            <coneGeometry args={[0.28, 1.1, 10, 1, true]} />
            <meshBasicMaterial
              color="#ffe9a0"
              transparent
              opacity={0.12}
              depthWrite={false}
              side={THREE.DoubleSide}
            />
          </mesh>
        </group>
      ))}
      {/* Real road wash — only on flagged cars to protect FPS */}
      {castHeadlight && (
        <pointLight position={[-1.15, 0.22, 0]} intensity={1.8} distance={6.5} color="#ffe9a0" decay={2} />
      )}

      {/* taillights */}
      {([-1, 1] as const).map((side) => (
        <mesh key={`tl-${side}`} position={[0.72, 0.24, side * 0.22]}>
          <boxGeometry args={[0.05, 0.07, 0.1]} />
          <meshBasicMaterial color="#ff2a6d" toneMapped={false} />
        </mesh>
      ))}

      {/* roof light bar */}
      <mesh position={[0.05, 0.58, 0]}>
        <boxGeometry args={[0.35, 0.03, 0.12]} />
        <meshBasicMaterial color={accent} toneMapped={false} />
      </mesh>

      {/* wheels */}
      {(
        [
          [-0.42, 0.11, 0.34],
          [-0.42, 0.11, -0.34],
          [0.42, 0.11, 0.34],
          [0.42, 0.11, -0.34],
        ] as const
      ).map((p, i) => (
        <group key={i} position={p} rotation={[0, i < 2 ? wheelYaw : 0, 0]}>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.12, 0.12, 0.1, 12]} />
            <meshBasicMaterial color="#0a0c10" />
          </mesh>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.06, 0.06, 0.11, 8]} />
            <meshBasicMaterial color="#8a93a8" />
          </mesh>
          {/* hub glow */}
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.03, 0.03, 0.12, 6]} />
            <meshBasicMaterial color={accent} toneMapped={false} />
          </mesh>
        </group>
      ))}

      {/* bot passengers — scaled desk bots riding shotgun */}
      {passengers.map((p, i) => (
        <group key={i} position={p.seat} scale={0.2} rotation={[0, -Math.PI / 2, 0]}>
          <BotFigure pose={p.pose} seated />
        </group>
      ))}
    </group>
  )
}
