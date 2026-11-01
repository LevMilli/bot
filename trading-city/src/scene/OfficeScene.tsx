import { useEffect, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow } from '../types'
import { GridFloor } from './GridFloor'
import { Skyline, Starfield } from './Skyline'
import { BotFigure } from './BotFigure'

type Props = {
  bot: BotRow
}

function MonitorFrame({
  position,
  rotation,
  size,
  edge,
}: {
  position: [number, number, number]
  rotation: [number, number, number]
  size: [number, number]
  edge: string
}) {
  const [w, h] = size
  return (
    <group position={position} rotation={rotation}>
      <mesh>
        <boxGeometry args={[w, h, 0.05]} />
        <meshStandardMaterial color="#03050c" emissive={edge} emissiveIntensity={0.18} metalness={0.4} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0, 0.03]}>
        <planeGeometry args={[w * 0.92, h * 0.88]} />
        <meshBasicMaterial color="#071018" transparent opacity={0.92} />
      </mesh>
      <mesh position={[0, 0, 0.028]}>
        <planeGeometry args={[w * 0.94, h * 0.9]} />
        <meshBasicMaterial color={edge} transparent opacity={0.12} />
      </mesh>
      {/* neon rim */}
      <mesh position={[0, h / 2 + 0.02, 0.02]}>
        <boxGeometry args={[w, 0.03, 0.03]} />
        <meshBasicMaterial color={edge} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.02, 0.02]}>
        <boxGeometry args={[w, 0.03, 0.03]} />
        <meshBasicMaterial color={edge} />
      </mesh>
    </group>
  )
}

export function OfficeScene({ bot }: Props) {
  const cam = useRef<Cam>(null)
  const celebrating = Number(bot.today || 0) > 0 || Number(bot.realized || 0) > 0 || bot.present !== false

  useEffect(() => {
    if (cam.current) {
      cam.current.position.set(0, 2.35, 5.4)
      cam.current.lookAt(0, 1.45, -0.4)
    }
  }, [bot.id])

  useFrame((_, dt) => {
    if (!cam.current) return
    const target = { x: 0.15, y: 2.15, z: 4.55 }
    cam.current.position.x += (target.x - cam.current.position.x) * Math.min(1, dt * 2.4)
    cam.current.position.y += (target.y - cam.current.position.y) * Math.min(1, dt * 2.4)
    cam.current.position.z += (target.z - cam.current.position.z) * Math.min(1, dt * 2.4)
    cam.current.lookAt(0, 1.4, -0.35)
  })

  return (
    <>
      <color attach="background" args={['#14052c']} />
      <fog attach="fog" args={['#1a0740', 14, 38]} />
      <PerspectiveCamera ref={cam} makeDefault fov={46} near={0.1} far={100} />
      <ambientLight intensity={0.35} />
      <directionalLight position={[3, 7, 4]} intensity={0.7} color="#dff" />
      <pointLight position={[0, 2.8, 1.2]} intensity={1.6} color="#2de2e6" distance={16} />
      <pointLight position={[-1.5, 2, 0.5]} intensity={0.7} color="#39ff14" distance={10} />

      <Starfield count={280} />
      <GridFloor size={48} />
      <Skyline z={-14} width={46} />

      {/* chair */}
      <mesh position={[0, 0.55, 0.85]}>
        <boxGeometry args={[0.7, 0.12, 0.7]} />
        <meshStandardMaterial color="#101018" />
      </mesh>
      <mesh position={[0, 1.05, 1.05]}>
        <boxGeometry args={[0.65, 0.9, 0.1]} />
        <meshStandardMaterial color="#12121c" emissive="#39ff14" emissiveIntensity={0.15} />
      </mesh>
      <mesh position={[0, 1.15, 1.12]}>
        <torusGeometry args={[0.12, 0.025, 8, 4]} />
        <meshBasicMaterial color="#c8ff9a" />
      </mesh>

      {/* desk */}
      <mesh position={[0, 0.78, -0.15]}>
        <boxGeometry args={[2.9, 0.1, 1.25]} />
        <meshStandardMaterial color="#0c0c16" emissive="#1a6cff" emissiveIntensity={0.12} metalness={0.35} roughness={0.4} />
      </mesh>
      <mesh position={[-1.05, 0.38, 0.25]}>
        <boxGeometry args={[0.1, 0.75, 0.1]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>
      <mesh position={[1.05, 0.38, 0.25]}>
        <boxGeometry args={[0.1, 0.75, 0.1]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>

      {/* red desk puck from ref */}
      <mesh position={[-0.85, 0.86, 0.15]} rotation={[-Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.16, 0.16, 0.05, 24]} />
        <meshStandardMaterial color="#c01028" emissive="#ff2040" emissiveIntensity={0.85} />
      </mesh>

      <MonitorFrame position={[-1.2, 1.45, -0.55]} rotation={[0, 0.28, 0]} size={[1.05, 0.78]} edge="#39ff14" />
      <MonitorFrame position={[0, 1.55, -0.72]} rotation={[0, 0, 0]} size={[1.4, 0.9]} edge="#2de2e6" />
      <MonitorFrame position={[1.2, 1.45, -0.55]} rotation={[0, -0.28, 0]} size={[1.05, 0.78]} edge="#39ff14" />

      <BotFigure celebrating={celebrating} />
    </>
  )
}
