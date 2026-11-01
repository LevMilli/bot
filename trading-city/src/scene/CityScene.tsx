import { useMemo, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow } from '../types'
import { GridFloor } from './GridFloor'
import { SkyEquityLine, Skyline, Starfield } from './Skyline'
import { Vault } from './Vault'
import { Tower } from './Tower'

export const RING_R = 7.6

type Props = {
  bots: BotRow[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function CityScene({ bots, selectedId, onSelect }: Props) {
  const cam = useRef<Cam>(null)

  const slots = useMemo(() => {
    const n = Math.max(bots.length, 5)
    return bots.map((bot, i) => {
      // Vault sits toward camera; towers arc behind / beside it.
      const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.12
      const x = Math.cos(a) * RING_R
      const z = Math.sin(a) * RING_R - 0.8
      return { bot, index: i, position: [x, 0, z] as [number, number, number] }
    })
  }, [bots])

  useFrame((_, dt) => {
    if (!cam.current) return
    // High-angle plaza shot matching the city overview reference.
    const target = { x: 0, y: 15.2, z: 15.2 }
    cam.current.position.x += (target.x - cam.current.position.x) * Math.min(1, dt * 1.8)
    cam.current.position.y += (target.y - cam.current.position.y) * Math.min(1, dt * 1.8)
    cam.current.position.z += (target.z - cam.current.position.z) * Math.min(1, dt * 1.8)
    cam.current.lookAt(0, 0.4, -0.5)
  })

  return (
    <>
      <color attach="background" args={['#0a0420']} />
      <fog attach="fog" args={['#160840', 24, 62]} />
      <PerspectiveCamera ref={cam} makeDefault fov={42} near={0.1} far={200} position={[0, 17, 15]} />
      <ambientLight intensity={0.28} />
      <directionalLight position={[6, 18, 8]} intensity={0.55} color="#a8c8ff" />
      <pointLight position={[0, 6, 6]} intensity={1.4} color="#ffe9a0" distance={28} />
      <pointLight position={[-8, 5, -4]} intensity={0.9} color="#ff2a6d" distance={30} />
      <pointLight position={[8, 5, -4]} intensity={0.7} color="#2de2e6" distance={30} />

      <Starfield />
      <GridFloor />
      <Skyline z={-22} width={72} />
      <Skyline z={-30} width={88} />
      <SkyEquityLine />
      <Vault />

      {slots.map(({ bot, index, position }) => (
        <Tower
          key={bot.id}
          bot={bot}
          index={index}
          position={position}
          selected={selectedId === bot.id}
          onSelect={onSelect}
        />
      ))}
    </>
  )
}
