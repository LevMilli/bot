import { useEffect, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow } from '../types'
import { GridFloor } from './GridFloor'
import { Skyline } from './Skyline'
import { BotFigure } from './BotFigure'

type Props = {
  bot: BotRow
}

export function OfficeScene({ bot }: Props) {
  const cam = useRef<Cam>(null)
  const celebrating = Number(bot.today || 0) > 0 || Number(bot.realized || 0) > 0

  useEffect(() => {
    if (cam.current) {
      cam.current.position.set(0, 2.2, 5.2)
      cam.current.lookAt(0, 1.4, 0)
    }
  }, [bot.id])

  useFrame((_, dt) => {
    if (!cam.current) return
    const target = { x: 0, y: 2.05, z: 4.6 }
    cam.current.position.x += (target.x - cam.current.position.x) * Math.min(1, dt * 2.2)
    cam.current.position.y += (target.y - cam.current.position.y) * Math.min(1, dt * 2.2)
    cam.current.position.z += (target.z - cam.current.position.z) * Math.min(1, dt * 2.2)
    cam.current.lookAt(0, 1.35, -0.2)
  })

  return (
    <>
      <color attach="background" args={['#14052c']} />
      <fog attach="fog" args={['#1a0740', 12, 42]} />
      <PerspectiveCamera ref={cam} makeDefault fov={48} near={0.1} far={100} />
      <ambientLight intensity={0.4} />
      <directionalLight position={[4, 8, 5]} intensity={0.9} color="#dff" />
      <pointLight position={[0, 3, 1]} intensity={1.4} color="#2de2e6" distance={18} />
      <GridFloor size={40} />
      <Skyline z={-16} width={50} />

      {/* desk */}
      <mesh position={[0, 0.72, -0.1]}>
        <boxGeometry args={[2.6, 0.12, 1.1]} />
        <meshStandardMaterial color="#10101c" emissive="#1a6cff" emissiveIntensity={0.15} />
      </mesh>
      <mesh position={[-0.9, 0.35, 0.2]}>
        <boxGeometry args={[0.12, 0.7, 0.12]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>
      <mesh position={[0.9, 0.35, 0.2]}>
        <boxGeometry args={[0.12, 0.7, 0.12]} />
        <meshStandardMaterial color="#1a1a28" />
      </mesh>

      {/* monitor frames (content is DOM HUD) */}
      {[
        [-1.15, 1.35, -0.55, 0.18],
        [0, 1.45, -0.7, 0],
        [1.15, 1.35, -0.55, -0.18],
      ].map(([x, y, z, rot], i) => (
        <mesh key={i} position={[x, y, z]} rotation={[0, rot, 0]}>
          <boxGeometry args={[i === 1 ? 1.35 : 1.05, i === 1 ? 0.85 : 0.75, 0.06]} />
          <meshStandardMaterial
            color="#050510"
            emissive={i === 1 ? '#2de2e6' : '#39ff14'}
            emissiveIntensity={0.25}
            metalness={0.5}
            roughness={0.3}
          />
        </mesh>
      ))}

      <BotFigure celebrating={celebrating} />
    </>
  )
}
