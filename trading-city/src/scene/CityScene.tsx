import { useMemo } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import type { BotRow } from '../types'
import { GridFloor } from './GridFloor'
import { Skyline } from './Skyline'
import { Vault } from './Vault'
import { Tower } from './Tower'

const RING_R = 9

type Props = {
  bots: BotRow[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function CityScene({ bots, selectedId, onSelect }: Props) {
  const slots = useMemo(() => {
    const n = Math.max(bots.length, 5)
    return bots.map((bot, i) => {
      const a = -Math.PI / 2 + (i / n) * Math.PI * 2
      const x = Math.cos(a) * RING_R
      const z = Math.sin(a) * RING_R - 1
      return { bot, index: i, position: [x, 0, z] as [number, number, number] }
    })
  }, [bots])

  return (
    <>
      <color attach="background" args={['#07021a']} />
      <fog attach="fog" args={['#12062e', 28, 75]} />
      <PerspectiveCamera makeDefault position={[0, 18, 22]} fov={42} near={0.1} far={200} />
      <ambientLight intensity={0.35} />
      <directionalLight position={[8, 20, 10]} intensity={0.85} color="#c8e7ff" />
      <pointLight position={[0, 8, 6]} intensity={1.2} color="#f9c80e" distance={40} />
      <pointLight position={[-10, 6, -8]} intensity={0.7} color="#ff2a6d" distance={35} />
      <GridFloor />
      <Skyline />
      <Skyline z={-34} width={90} />
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
