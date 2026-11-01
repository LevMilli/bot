import { useEffect, useMemo, useRef } from 'react'
import { PerspectiveCamera, RenderTexture } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam, Texture } from 'three'
import type { BotRow, Desk } from '../types'
import {
  centerMonitorTexture,
  leftMonitorTexture,
  rightMonitorTexture,
} from '../hud/monitorTextures'
import { NeonBloom } from './Effects'
import { BotFigure } from './BotFigure'
import { CityGlass } from './WindowCity'

type Props = {
  bot: BotRow
  bots: BotRow[]
  desk?: Desk
}

const FRAME = '#243044'
const WALL = '#2c3548'
const TRIM = '#8ea0b8'

function MonitorFrame({
  position,
  rotation,
  size,
  edge,
  map,
}: {
  position: [number, number, number]
  rotation: [number, number, number]
  size: [number, number]
  edge: string
  map: Texture
}) {
  const [w, h] = size
  return (
    <group position={position} rotation={rotation}>
      <mesh>
        <boxGeometry args={[w, h, 0.05]} />
        <meshStandardMaterial color="#0c1018" metalness={0.35} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, 0.028]}>
        <planeGeometry args={[w * 0.9, h * 0.84]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, h / 2 + 0.012, 0.02]}>
        <boxGeometry args={[w + 0.03, 0.022, 0.03]} />
        <meshBasicMaterial color={edge} toneMapped={false} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.012, 0.02]}>
        <boxGeometry args={[w + 0.03, 0.022, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[-w / 2 - 0.012, 0, 0.02]}>
        <boxGeometry args={[0.022, h + 0.02, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[w / 2 + 0.012, 0, 0.02]}>
        <boxGeometry args={[0.022, h + 0.02, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      {/* stand */}
      <mesh position={[0, -h / 2 - 0.16, 0.04]}>
        <boxGeometry args={[0.06, 0.26, 0.06]} />
        <meshStandardMaterial color="#1c222e" metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.28, 0.06]}>
        <boxGeometry args={[0.28, 0.02, 0.16]} />
        <meshStandardMaterial color="#1c222e" metalness={0.55} roughness={0.35} />
      </mesh>
    </group>
  )
}

function Ceiling() {
  const tiles: [number, number][] = []
  for (let x = -2; x <= 2; x++) {
    for (let z = -1; z <= 2; z++) {
      tiles.push([x * 1.55, z * 1.35 - 0.4])
    }
  }
  return (
    <group>
      <mesh position={[0, 3.38, 0.7]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[16, 8.2]} />
        <meshStandardMaterial color="#1a1e28" roughness={0.92} />
      </mesh>
      {tiles.map(([x, z]) => (
        <mesh key={`${x}-${z}`} position={[x, 3.36, z]} rotation={[Math.PI / 2, 0, 0]}>
          <planeGeometry args={[1.42, 1.18]} />
          <meshStandardMaterial color="#222733" roughness={0.85} metalness={0.04} />
        </mesh>
      ))}
      {/* troffer lights */}
      {([-1.15, 1.15] as const).map((x) => (
        <mesh key={x} position={[x, 3.34, 0.35]}>
          <boxGeometry args={[0.28, 0.04, 2.6]} />
          <meshBasicMaterial color="#e7f6ff" toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

function SideWall({ x, rot }: { x: number; rot: number }) {
  return (
    <group position={[x, 1.69, 0.7]} rotation={[0, rot, 0]}>
      <mesh>
        <planeGeometry args={[8.2, 3.38]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      <mesh position={[0, -0.85, 0.01]}>
        <planeGeometry args={[8.2, 1.35]} />
        <meshStandardMaterial color="#1b212e" roughness={0.82} />
      </mesh>
      <mesh position={[0, -0.16, 0.02]}>
        <boxGeometry args={[8.2, 0.04, 0.02]} />
        <meshStandardMaterial color={TRIM} metalness={0.35} roughness={0.45} />
      </mesh>
      <mesh position={[0, -1.66, 0.02]}>
        <boxGeometry args={[8.2, 0.06, 0.03]} />
        <meshStandardMaterial color="#0d1118" metalness={0.4} roughness={0.4} />
      </mesh>
    </group>
  )
}

function Door() {
  return (
    <group position={[-7.85, 1.15, 1.35]} rotation={[0, Math.PI / 2, 0]}>
      <mesh position={[0, 0, 0.02]}>
        <boxGeometry args={[1.05, 2.25, 0.06]} />
        <meshStandardMaterial color="#0e121a" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0, 0.06]}>
        <boxGeometry args={[0.92, 2.12, 0.02]} />
        <meshStandardMaterial color="#171c28" roughness={0.6} />
      </mesh>
      <mesh position={[0.32, 0, 0.09]}>
        <boxGeometry args={[0.04, 0.16, 0.04]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
      </mesh>
    </group>
  )
}

function Credenza() {
  return (
    <group position={[3.15, 0.42, -1.15]}>
      <mesh>
        <boxGeometry args={[0.55, 0.78, 1.7]} />
        <meshStandardMaterial color="#161b26" metalness={0.25} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.08, 0.28]}>
        <boxGeometry args={[0.52, 0.02, 0.7]} />
        <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, -0.22, 0.28]}>
        <boxGeometry args={[0.52, 0.02, 0.7]} />
        <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[-0.28, 0.55, 0]}>
        <boxGeometry args={[0.02, 0.28, 0.02]} />
        <meshStandardMaterial color="#9aa3b5" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[-0.28, 0.7, 0]}>
        <boxGeometry args={[0.16, 0.03, 0.16]} />
        <meshStandardMaterial color="#123" emissive="#1a6a44" emissiveIntensity={0.4} roughness={0.6} />
      </mesh>
      <mesh position={[-0.28, 0.86, 0]}>
        <sphereGeometry args={[0.1, 10, 10]} />
        <meshStandardMaterial color="#1d6b45" roughness={0.7} />
      </mesh>
    </group>
  )
}

function OfficeChair() {
  const spokes = [0, 1, 2, 3, 4]
  return (
    <group position={[0, 0, 0.62]}>
      <mesh position={[0, 0.28, 0]}>
        <cylinderGeometry args={[0.045, 0.05, 0.36, 12]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.85} roughness={0.22} />
      </mesh>
      {spokes.map((i) => {
        const a = (i / 5) * Math.PI * 2
        return (
          <group key={i} rotation={[0, a, 0]}>
            <mesh position={[0.18, 0.08, 0]}>
              <boxGeometry args={[0.32, 0.035, 0.05]} />
              <meshStandardMaterial color="#141820" metalness={0.5} roughness={0.4} />
            </mesh>
            <mesh position={[0.34, 0.05, 0]}>
              <sphereGeometry args={[0.045, 10, 10]} />
              <meshStandardMaterial color="#0c0e14" roughness={0.45} />
            </mesh>
          </group>
        )
      })}
      <mesh position={[0, 0.48, 0.02]}>
        <boxGeometry args={[0.62, 0.08, 0.58]} />
        <meshStandardMaterial color="#12151c" roughness={0.7} />
      </mesh>
      {/* Lumbar only — the pack and its cross stay visible above it. */}
      <mesh position={[0, 0.4, 0.2]}>
        <boxGeometry args={[0.46, 0.16, 0.05]} />
        <meshStandardMaterial color="#1c2433" roughness={0.6} />
      </mesh>
      {([-0.36, 0.36] as const).map((x) => (
        <group key={x}>
          <mesh position={[x, 0.68, 0.02]}>
            <boxGeometry args={[0.05, 0.28, 0.05]} />
            <meshStandardMaterial color="#1c222e" metalness={0.4} roughness={0.4} />
          </mesh>
          <mesh position={[x, 0.82, 0.04]}>
            <boxGeometry args={[0.08, 0.035, 0.32]} />
            <meshStandardMaterial color="#1c222e" metalness={0.4} roughness={0.4} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

function WindowWall({ bots }: { bots: BotRow[] }) {
  return (
    <group position={[0, 0, -3.55]}>
      {/* opaque surround */}
      <mesh position={[0, 3.28, 0]}>
        <boxGeometry args={[16, 0.28, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      <mesh position={[0, 0.38, 0]}>
        <boxGeometry args={[16, 0.76, 0.16]} />
        <meshStandardMaterial color="#3a455c" roughness={0.8} />
      </mesh>
      <mesh position={[-5.7, 1.9, 0]}>
        <boxGeometry args={[4.6, 2.7, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      <mesh position={[5.7, 1.9, 0]}>
        <boxGeometry args={[4.6, 2.7, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>

      {/* curtain-wall frame */}
      <mesh position={[0, 0.78, 0.04]}>
        <boxGeometry args={[7.05, 0.08, 0.08]} />
        <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, 3.12, 0.04]}>
        <boxGeometry args={[7.05, 0.08, 0.08]} />
        <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
      </mesh>
      {([-3.48, 3.48] as const).map((x) => (
        <mesh key={x} position={[x, 1.95, 0.04]}>
          <boxGeometry args={[0.08, 2.42, 0.08]} />
          <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
        </mesh>
      ))}
      {([-1.15, 1.15] as const).map((x) => (
        <mesh key={`m-${x}`} position={[x, 1.95, 0.07]}>
          <boxGeometry args={[0.045, 2.28, 0.05]} />
          <meshStandardMaterial color="#8b95a8" metalness={0.7} roughness={0.28} />
        </mesh>
      ))}

      {/* glass: live city overlook */}
      <mesh position={[0, 1.95, 0.02]} raycast={() => null}>
        <planeGeometry args={[6.82, 2.26]} />
        <meshBasicMaterial toneMapped={false}>
          <RenderTexture attach="map" width={1536} height={512} anisotropy={8}>
            <CityGlass bots={bots} />
          </RenderTexture>
        </meshBasicMaterial>
      </mesh>
      {/* faint glass sheen in front of the mullions' plane */}
      <mesh position={[0, 1.95, 0.09]} raycast={() => null}>
        <planeGeometry args={[6.82, 2.26]} />
        <meshBasicMaterial color="#b7fff8" transparent opacity={0.05} depthWrite={false} />
      </mesh>

      {/* exterior sill */}
      <mesh position={[0, 0.72, -0.18]}>
        <boxGeometry args={[7.2, 0.06, 0.28]} />
        <meshStandardMaterial color="#0e1218" metalness={0.4} roughness={0.45} />
      </mesh>
    </group>
  )
}

function Desk() {
  return (
    <group>
      <mesh position={[0, 0.76, -0.15]}>
        <boxGeometry args={[3.7, 0.08, 1.45]} />
        <meshStandardMaterial color="#12151c" metalness={0.35} roughness={0.42} />
      </mesh>
      <mesh position={[0, 0.72, 0.52]}>
        <boxGeometry args={[3.7, 0.025, 0.04]} />
        <meshStandardMaterial color="#2de2e6" emissive="#2de2e6" emissiveIntensity={0.35} metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.42, -0.72]}>
        <boxGeometry args={[3.55, 0.58, 0.06]} />
        <meshStandardMaterial color="#10141c" roughness={0.75} />
      </mesh>
      {([-1.55, 1.55] as const).map((x) => (
        <mesh key={x} position={[x, 0.38, 0.15]}>
          <boxGeometry args={[0.08, 0.72, 1.15]} />
          <meshStandardMaterial color="#1a1f2a" metalness={0.3} roughness={0.5} />
        </mesh>
      ))}
      <mesh position={[0.15, 0.81, 0.15]}>
        <boxGeometry args={[0.55, 0.02, 0.2]} />
        <meshStandardMaterial color="#0c0e14" roughness={0.5} />
      </mesh>
      <mesh position={[-0.95, 0.82, 0.28]} rotation={[-Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.13, 0.13, 0.045, 24]} />
        <meshStandardMaterial color="#c01028" emissive="#ff2040" emissiveIntensity={0.7} roughness={0.35} />
      </mesh>
    </group>
  )
}

function OfficeFloor() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0.7]}>
        <planeGeometry args={[16, 8.3]} />
        <meshStandardMaterial color="#1a2230" roughness={0.72} metalness={0.12} />
      </mesh>
      <gridHelper args={[8, 16, '#1a6a78', '#142033']} position={[0, 0.012, 0.55]} />
    </group>
  )
}

export function OfficeScene({ bot, bots, desk }: Props) {
  const cam = useRef<Cam>(null)
  const celebrating = Number(bot.today || 0) > 0 || Number(bot.realized || 0) > 0 || bot.present !== false

  const maps = useMemo(() => {
    const left = leftMonitorTexture(bot)
    const center = centerMonitorTexture(bot, desk)
    const right = rightMonitorTexture(bot)
    return { left, center, right }
  }, [bot, desk])

  useEffect(() => {
    return () => {
      maps.left.dispose()
      maps.center.dispose()
      maps.right.dispose()
    }
  }, [maps])

  useEffect(() => {
    if (cam.current) {
      cam.current.position.set(0.05, 1.72, 3.55)
      cam.current.lookAt(0, 1.55, 0.4)
    }
  }, [bot.id])

  useFrame((_, dt) => {
    if (!cam.current) return
    const target = { x: 0.05, y: 1.72, z: 3.55 }
    cam.current.position.x += (target.x - cam.current.position.x) * Math.min(1, dt * 2.2)
    cam.current.position.y += (target.y - cam.current.position.y) * Math.min(1, dt * 2.2)
    cam.current.position.z += (target.z - cam.current.position.z) * Math.min(1, dt * 2.2)
    cam.current.lookAt(0, 1.55, 0.4)
  })

  return (
    <>
      <color attach="background" args={['#070b14']} />
      <PerspectiveCamera ref={cam} makeDefault fov={46} near={0.1} far={80} />
      <ambientLight intensity={0.62} color="#d5deee" />
      <directionalLight position={[1.5, 4.2, 2]} intensity={0.7} color="#f2f6ff" />
      <pointLight position={[-1.15, 3.15, 0.4]} intensity={0.7} color="#e7f4ff" distance={8} />
      <pointLight position={[1.15, 3.15, 0.4]} intensity={0.7} color="#e7f4ff" distance={8} />
      <pointLight position={[0, 1.9, -2.4]} intensity={0.45} color="#7ef9ff" distance={7} />

      <OfficeFloor />
      <Ceiling />
      <SideWall x={-7.9} rot={Math.PI / 2} />
      <SideWall x={7.9} rot={-Math.PI / 2} />
      <mesh position={[0, 1.69, 4.8]} rotation={[0, Math.PI, 0]}>
        <planeGeometry args={[16, 3.38]} />
        <meshStandardMaterial color="#10141c" roughness={0.92} />
      </mesh>
      <Door />
      <Credenza />
      <WindowWall bots={bots} />
      <Desk />
      <OfficeChair />

      <MonitorFrame position={[-1.55, 1.28, -0.62]} rotation={[0, 0.22, 0]} size={[1.02, 0.64]} edge="#39ff14" map={maps.left} />
      <MonitorFrame position={[0.02, 1.4, -0.88]} rotation={[-0.08, 0, 0]} size={[1.22, 0.72]} edge="#2de2e6" map={maps.center} />
      <MonitorFrame position={[1.58, 1.28, -0.62]} rotation={[0, -0.22, 0]} size={[1.02, 0.64]} edge="#39ff14" map={maps.right} />

      <BotFigure celebrating={celebrating} />
      <NeonBloom strength={0.42} />
    </>
  )
}
