import { useEffect, useMemo, useRef, type ReactNode } from 'react'
import { Html, PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow, Desk } from '../types'
import { NeonBloom } from './Effects'
import { GridFloor } from './GridFloor'
import { Skyline, Starfield } from './Skyline'
import { BotFigure } from './BotFigure'
import { MonitorPanels } from '../hud/Monitors'

type Props = {
  bot: BotRow
  desk?: Desk
}

function MonitorFrame({
  position,
  rotation,
  size,
  edge,
  children,
}: {
  position: [number, number, number]
  rotation: [number, number, number]
  size: [number, number]
  edge: string
  children?: ReactNode
}) {
  const [w, h] = size
  return (
    <group position={position} rotation={rotation}>
      <mesh>
        <boxGeometry args={[w, h, 0.06]} />
        <meshStandardMaterial color="#03050c" emissive={edge} emissiveIntensity={0.22} metalness={0.45} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0, 0.032]}>
        <planeGeometry args={[w * 0.92, h * 0.88]} />
        <meshBasicMaterial color="#050b14" />
      </mesh>
      {/* neon rim */}
      <mesh position={[0, h / 2 + 0.015, 0.02]}>
        <boxGeometry args={[w + 0.04, 0.028, 0.028]} />
        <meshBasicMaterial color={edge} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.015, 0.02]}>
        <boxGeometry args={[w + 0.04, 0.028, 0.028]} />
        <meshBasicMaterial color={edge} />
      </mesh>
      <mesh position={[-w / 2 - 0.015, 0, 0.02]}>
        <boxGeometry args={[0.028, h + 0.04, 0.028]} />
        <meshBasicMaterial color={edge} />
      </mesh>
      <mesh position={[w / 2 + 0.015, 0, 0.02]}>
        <boxGeometry args={[0.028, h + 0.04, 0.028]} />
        <meshBasicMaterial color={edge} />
      </mesh>
      {children && (
        <Html
          transform
          position={[0, 0, 0.04]}
          distanceFactor={1.35}
          style={{ width: `${w * 120}px`, height: `${h * 120}px`, pointerEvents: 'none' }}
          occlude={false}
        >
          <div className="monitor-glass" style={{ borderColor: edge }}>
            {children}
          </div>
        </Html>
      )}
    </group>
  )
}

function RoomShell() {
  return (
    <group>
      {/* side walls */}
      <mesh position={[-5.2, 2.4, -1]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[10, 5.2]} />
        <meshStandardMaterial color="#0a0420" roughness={0.95} />
      </mesh>
      <mesh position={[5.2, 2.4, -1]} rotation={[0, -Math.PI / 2, 0]}>
        <planeGeometry args={[10, 5.2]} />
        <meshStandardMaterial color="#0a0420" roughness={0.95} />
      </mesh>
      {/* ceiling strip */}
      <mesh position={[0, 4.6, -1]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[10.5, 10]} />
        <meshStandardMaterial color="#070218" roughness={1} />
      </mesh>
      {/* window frame around skyline */}
      <mesh position={[0, 2.6, -6.6]}>
        <boxGeometry args={[9.2, 4.4, 0.12]} />
        <meshStandardMaterial color="#10101c" emissive="#2de2e6" emissiveIntensity={0.08} />
      </mesh>
      <mesh position={[0, 2.6, -6.55]}>
        <planeGeometry args={[8.4, 3.7]} />
        <meshBasicMaterial color="#14052c" transparent opacity={0.15} depthWrite={false} />
      </mesh>
      {/* cyan window trim */}
      <mesh position={[0, 4.45, -6.5]}>
        <boxGeometry args={[8.6, 0.06, 0.06]} />
        <meshBasicMaterial color="#2de2e6" />
      </mesh>
      <mesh position={[0, 0.75, -6.5]}>
        <boxGeometry args={[8.6, 0.06, 0.06]} />
        <meshBasicMaterial color="#2de2e6" />
      </mesh>
      <mesh position={[-4.25, 2.6, -6.5]}>
        <boxGeometry args={[0.06, 3.8, 0.06]} />
        <meshBasicMaterial color="#2de2e6" />
      </mesh>
      <mesh position={[4.25, 2.6, -6.5]}>
        <boxGeometry args={[0.06, 3.8, 0.06]} />
        <meshBasicMaterial color="#2de2e6" />
      </mesh>
    </group>
  )
}

export function OfficeScene({ bot, desk }: Props) {
  const cam = useRef<Cam>(null)
  const celebrating = Number(bot.today || 0) > 0 || Number(bot.realized || 0) > 0 || bot.present !== false
  const panels = useMemo(() => MonitorPanels({ bot, desk }), [bot, desk])

  useEffect(() => {
    if (cam.current) {
      cam.current.position.set(0, 2.35, 5.4)
      cam.current.lookAt(0, 1.45, -0.4)
    }
  }, [bot.id])

  useFrame((_, dt) => {
    if (!cam.current) return
    const target = { x: 0.12, y: 2.05, z: 4.35 }
    cam.current.position.x += (target.x - cam.current.position.x) * Math.min(1, dt * 2.4)
    cam.current.position.y += (target.y - cam.current.position.y) * Math.min(1, dt * 2.4)
    cam.current.position.z += (target.z - cam.current.position.z) * Math.min(1, dt * 2.4)
    cam.current.lookAt(0, 1.35, -0.45)
  })

  return (
    <>
      <color attach="background" args={['#14052c']} />
      <fog attach="fog" args={['#1a0740', 12, 34]} />
      <PerspectiveCamera ref={cam} makeDefault fov={46} near={0.1} far={100} />
      <ambientLight intensity={0.32} />
      <directionalLight position={[3, 7, 4]} intensity={0.65} color="#dff" />
      <pointLight position={[0, 2.8, 1.2]} intensity={1.8} color="#2de2e6" distance={16} />
      <pointLight position={[-1.5, 2, 0.5]} intensity={0.85} color="#39ff14" distance={10} />
      <pointLight position={[1.2, 2.2, 0.2]} intensity={0.55} color="#f9c80e" distance={8} />

      <Starfield count={420} />
      <GridFloor size={48} plaza={false} />
      <Skyline z={-14} width={46} />
      <RoomShell />

      {/* chair */}
      <mesh position={[0, 0.52, 0.88]}>
        <boxGeometry args={[0.78, 0.1, 0.72]} />
        <meshStandardMaterial color="#0c0c14" metalness={0.25} roughness={0.5} />
      </mesh>
      <mesh position={[0, 1.08, 1.12]}>
        <boxGeometry args={[0.72, 1.05, 0.1]} />
        <meshStandardMaterial color="#101018" emissive="#39ff14" emissiveIntensity={0.12} />
      </mesh>
      <mesh position={[0, 1.35, 1.18]}>
        <torusGeometry args={[0.14, 0.028, 8, 16]} />
        <meshBasicMaterial color="#c8ff9a" />
      </mesh>
      {/* chair stem */}
      <mesh position={[0, 0.28, 0.88]}>
        <cylinderGeometry args={[0.08, 0.12, 0.4, 10]} />
        <meshStandardMaterial color="#1a1a28" metalness={0.5} roughness={0.35} />
      </mesh>

      {/* desk */}
      <mesh position={[0, 0.78, -0.15]}>
        <boxGeometry args={[3.05, 0.1, 1.3]} />
        <meshStandardMaterial color="#0a0a14" emissive="#1a6cff" emissiveIntensity={0.1} metalness={0.4} roughness={0.38} />
      </mesh>
      <mesh position={[-1.15, 0.38, 0.25]}>
        <boxGeometry args={[0.1, 0.75, 0.1]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>
      <mesh position={[1.15, 0.38, 0.25]}>
        <boxGeometry args={[0.1, 0.75, 0.1]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>

      {/* red desk puck from ref */}
      <mesh position={[-0.9, 0.86, 0.18]} rotation={[-Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.15, 0.15, 0.05, 24]} />
        <meshStandardMaterial color="#c01028" emissive="#ff2040" emissiveIntensity={0.95} />
      </mesh>

      <MonitorFrame position={[-1.25, 1.48, -0.55]} rotation={[0, 0.32, 0]} size={[1.12, 0.82]} edge="#39ff14">
        {panels.left}
      </MonitorFrame>
      <MonitorFrame position={[0, 1.58, -0.75]} rotation={[0, 0, 0]} size={[1.48, 0.95]} edge="#2de2e6">
        {panels.center}
      </MonitorFrame>
      <MonitorFrame position={[1.25, 1.48, -0.55]} rotation={[0, -0.32, 0]} size={[1.12, 0.82]} edge="#39ff14">
        {panels.right}
      </MonitorFrame>

      <BotFigure celebrating={celebrating} />
      <NeonBloom strength={0.85} />
    </>
  )
}
