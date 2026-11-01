import { useEffect, useMemo, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam, Texture } from 'three'
import type { BotRow, Desk } from '../types'
import {
  centerMonitorTexture,
  leftMonitorTexture,
  rightMonitorTexture,
} from '../hud/monitorTextures'
import { NeonBloom } from './Effects'
import { GridFloor } from './GridFloor'
import { Skyline, Starfield } from './Skyline'
import { BotFigure } from './BotFigure'

type Props = {
  bot: BotRow
  desk?: Desk
}

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
        <boxGeometry args={[w, h, 0.06]} />
        <meshStandardMaterial color="#03050c" emissive={edge} emissiveIntensity={0.22} metalness={0.45} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0, 0.034]}>
        <planeGeometry args={[w * 0.92, h * 0.88]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, h / 2 + 0.015, 0.02]}>
        <boxGeometry args={[w + 0.04, 0.028, 0.028]} />
        <meshBasicMaterial color={edge} toneMapped={false} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.015, 0.02]}>
        <boxGeometry args={[w + 0.04, 0.028, 0.028]} />
        <meshBasicMaterial color={edge} toneMapped={false} />
      </mesh>
      <mesh position={[-w / 2 - 0.015, 0, 0.02]}>
        <boxGeometry args={[0.028, h + 0.04, 0.028]} />
        <meshBasicMaterial color={edge} toneMapped={false} />
      </mesh>
      <mesh position={[w / 2 + 0.015, 0, 0.02]}>
        <boxGeometry args={[0.028, h + 0.04, 0.028]} />
        <meshBasicMaterial color={edge} toneMapped={false} />
      </mesh>
    </group>
  )
}

function RoomShell() {
  return (
    <group>
      <mesh position={[-5.2, 2.4, -1]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[10, 5.2]} />
        <meshStandardMaterial color="#0a0420" roughness={0.95} />
      </mesh>
      <mesh position={[5.2, 2.4, -1]} rotation={[0, -Math.PI / 2, 0]}>
        <planeGeometry args={[10, 5.2]} />
        <meshStandardMaterial color="#0a0420" roughness={0.95} />
      </mesh>
      <mesh position={[0, 4.6, -1]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[10.5, 10]} />
        <meshStandardMaterial color="#070218" roughness={1} />
      </mesh>
      <mesh position={[0, 2.6, -6.6]}>
        <boxGeometry args={[9.2, 4.4, 0.12]} />
        <meshStandardMaterial color="#10101c" emissive="#2de2e6" emissiveIntensity={0.08} />
      </mesh>
      <mesh position={[0, 2.6, -6.55]}>
        <planeGeometry args={[8.4, 3.7]} />
        <meshBasicMaterial color="#14052c" transparent opacity={0.15} depthWrite={false} />
      </mesh>
      <mesh position={[0, 4.45, -6.5]}>
        <boxGeometry args={[8.6, 0.06, 0.06]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.75, -6.5]}>
        <boxGeometry args={[8.6, 0.06, 0.06]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <mesh position={[-4.25, 2.6, -6.5]}>
        <boxGeometry args={[0.06, 3.8, 0.06]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
      <mesh position={[4.25, 2.6, -6.5]}>
        <boxGeometry args={[0.06, 3.8, 0.06]} />
        <meshBasicMaterial color="#2de2e6" toneMapped={false} />
      </mesh>
    </group>
  )
}

export function OfficeScene({ bot, desk }: Props) {
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
      cam.current.position.set(0.45, 2.55, 5.2)
      cam.current.lookAt(0, 1.5, 0.1)
    }
  }, [bot.id])

  useFrame((_, dt) => {
    if (!cam.current) return
    const target = { x: 0.4, y: 2.45, z: 5.05 }
    cam.current.position.x += (target.x - cam.current.position.x) * Math.min(1, dt * 2.4)
    cam.current.position.y += (target.y - cam.current.position.y) * Math.min(1, dt * 2.4)
    cam.current.position.z += (target.z - cam.current.position.z) * Math.min(1, dt * 2.4)
    cam.current.lookAt(0, 1.5, 0.05)
  })

  return (
    <>
      <color attach="background" args={['#14052c']} />
      <fog attach="fog" args={['#1a0740', 14, 36]} />
      <PerspectiveCamera ref={cam} makeDefault fov={46} near={0.1} far={100} />
      <ambientLight intensity={0.45} />
      <directionalLight position={[3, 7, 4]} intensity={0.85} color="#e8f4ff" />
      <pointLight position={[0, 2.8, 1.2]} intensity={1.4} color="#2de2e6" distance={16} />
      <pointLight position={[-1.5, 2.2, 1.2]} intensity={0.9} color="#7ae8ff" distance={10} />
      <pointLight position={[1.2, 2.2, 0.2]} intensity={0.45} color="#f9c80e" distance={8} />

      <Starfield count={420} />
      <GridFloor size={48} plaza={false} />
      <Skyline z={-14} width={46} />
      <RoomShell />

      {/* chair behind bot */}
      <mesh position={[0, 0.52, 1.15]}>
        <boxGeometry args={[0.78, 0.1, 0.72]} />
        <meshStandardMaterial color="#0c0c14" metalness={0.25} roughness={0.5} />
      </mesh>
      <mesh position={[0, 1.2, 1.42]}>
        <boxGeometry args={[0.68, 1.05, 0.08]} />
        <meshStandardMaterial color="#0a0a12" roughness={0.7} />
      </mesh>
      <mesh position={[0, 0.28, 1.15]}>
        <cylinderGeometry args={[0.08, 0.12, 0.4, 10]} />
        <meshStandardMaterial color="#1a1a28" metalness={0.5} roughness={0.35} />
      </mesh>

      {/* desk */}
      <mesh position={[0, 0.78, -0.2]}>
        <boxGeometry args={[3.05, 0.1, 1.3]} />
        <meshStandardMaterial color="#0a0a14" emissive="#1a6cff" emissiveIntensity={0.1} metalness={0.4} roughness={0.38} />
      </mesh>
      <mesh position={[-1.15, 0.38, 0.2]}>
        <boxGeometry args={[0.1, 0.75, 0.1]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>
      <mesh position={[1.15, 0.38, 0.2]}>
        <boxGeometry args={[0.1, 0.75, 0.1]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>

      <mesh position={[-0.9, 0.86, 0.12]} rotation={[-Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.15, 0.15, 0.05, 24]} />
        <meshStandardMaterial color="#c01028" emissive="#ff2040" emissiveIntensity={0.95} />
      </mesh>

      <MonitorFrame position={[-1.3, 1.55, -0.6]} rotation={[0, 0.34, 0]} size={[1.12, 0.82]} edge="#39ff14" map={maps.left} />
      <MonitorFrame position={[0, 1.65, -0.82]} rotation={[0, 0, 0]} size={[1.48, 0.95]} edge="#2de2e6" map={maps.center} />
      <MonitorFrame position={[1.3, 1.55, -0.6]} rotation={[0, -0.34, 0]} size={[1.12, 0.82]} edge="#39ff14" map={maps.right} />

      <BotFigure celebrating={celebrating} />
      <NeonBloom strength={0.55} />
    </>
  )
}
