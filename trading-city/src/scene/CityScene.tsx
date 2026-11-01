import { useMemo, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow } from '../types'
import { NeonBloom } from './Effects'
import { GridFloor } from './GridFloor'
import { PurpleHorizon, SkyEquityLine, Skyline, Starfield } from './Skyline'
import { Vault } from './Vault'
import { FillerTower, Tower } from './Tower'

export const RING_R = 7.6

type Props = {
  bots: BotRow[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export type CitySlot = {
  bot: BotRow
  index: number
  position: [number, number, number]
}

export type FillerSlot = {
  position: [number, number, number]
  height: number
  width: number
  seed: number
}

function rand(seed: number) {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

/** Same plaza layout the city camera uses, so the office window matches the live city. */
export function layoutCity(bots: BotRow[]): { slots: CitySlot[]; fillers: FillerSlot[] } {
  const n = Math.max(bots.length, 5)
  const slots = bots.map((bot, i) => {
    // Vault sits toward camera; towers arc behind / beside it.
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.12
    const x = Math.cos(a) * RING_R
    const z = Math.sin(a) * RING_R - 0.8
    return { bot, index: i, position: [x, 0, z] as [number, number, number] }
  })

  const fillers: FillerSlot[] = []
  for (let i = 0; i < 10; i++) {
    const a = (i / 10) * Math.PI * 2 + 0.35
    const r = 2.8 + rand(i + 2) * 1.6
    fillers.push({
      position: [Math.cos(a) * r, 0, Math.sin(a) * r - 0.6],
      height: 3.2 + rand(i + 9) * 4.5,
      width: 0.85 + rand(i + 4) * 0.7,
      seed: i + 20,
    })
  }
  for (let i = 0; i < 16; i++) {
    const a = (i / 16) * Math.PI * 2 + 0.08
    const r = 9.4 + rand(i + 1) * 1.4
    const nearBot = slots.some((s) => {
      const dx = s.position[0] - Math.cos(a) * r
      const dz = s.position[2] - (Math.sin(a) * r - 1)
      return dx * dx + dz * dz < 4.5
    })
    if (nearBot) continue
    fillers.push({
      position: [Math.cos(a) * r, 0, Math.sin(a) * r - 1],
      height: 2.8 + rand(i + 11) * 5.2,
      width: 0.7 + rand(i + 6) * 1.1,
      seed: i + 40,
    })
  }
  return { slots, fillers }
}

export function CityScene({ bots, selectedId, onSelect }: Props) {
  const cam = useRef<Cam>(null)

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
      <color attach="background" args={['#0c0424']} />
      <fog attach="fog" args={['#1a0740', 28, 72]} />
      <PerspectiveCamera ref={cam} makeDefault fov={42} near={0.1} far={200} position={[0, 17, 15]} />
      <CityContents bots={bots} selectedId={selectedId} onSelect={onSelect} />
      <NeonBloom />
    </>
  )
}

/** Plaza, towers, vault, and sky for the city camera. The office window uses its own street view. */
export function CityContents({
  bots,
  selectedId,
  onSelect,
}: {
  bots: BotRow[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const { slots, fillers } = useMemo(() => layoutCity(bots), [bots])
  return (
    <>
      <ambientLight intensity={0.22} />
      <directionalLight position={[6, 18, 8]} intensity={0.45} color="#a8c8ff" />
      <pointLight position={[0, 6, 6]} intensity={1.6} color="#ffe9a0" distance={28} />
      <pointLight position={[-8, 5, -4]} intensity={1.05} color="#ff2a6d" distance={30} />
      <pointLight position={[8, 5, -4]} intensity={0.85} color="#2de2e6" distance={30} />
      <pointLight position={[0, 10, -8]} intensity={0.55} color="#b967ff" distance={40} />

      <PurpleHorizon />
      <Starfield />
      <GridFloor />
      <Skyline z={-22} width={72} />
      <Skyline z={-30} width={88} />
      <SkyEquityLine />
      <Vault />

      {fillers.map((f, i) => (
        <FillerTower key={`f-${i}`} {...f} />
      ))}

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
