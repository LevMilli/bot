import { useMemo } from 'react'
import type { BotRow } from '../types'
import { NeonBloom } from './Effects'
import { GridFloor } from './GridFloor'
import { PurpleHorizon, SkyEquityLine, Skyline, Starfield } from './Skyline'
import { Vault } from './Vault'
import { FillerTower, Tower } from './Tower'
import { CityOrbitCamera } from './CityControls'

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
  for (let i = 0; i < 14; i++) {
    const a = (i / 14) * Math.PI * 2 + 0.35
    const r = 2.6 + rand(i + 2) * 1.8
    fillers.push({
      position: [Math.cos(a) * r, 0, Math.sin(a) * r - 0.6],
      height: 3.4 + rand(i + 9) * 5.2,
      width: 0.8 + rand(i + 4) * 0.85,
      seed: i + 20,
    })
  }
  for (let i = 0; i < 22; i++) {
    const a = (i / 22) * Math.PI * 2 + 0.08
    const r = 9.2 + rand(i + 1) * 1.8
    const nearBot = slots.some((s) => {
      const dx = s.position[0] - Math.cos(a) * r
      const dz = s.position[2] - (Math.sin(a) * r - 1)
      return dx * dx + dz * dz < 4.5
    })
    if (nearBot) continue
    fillers.push({
      position: [Math.cos(a) * r, 0, Math.sin(a) * r - 1],
      height: 2.8 + rand(i + 11) * 5.8,
      width: 0.65 + rand(i + 6) * 1.2,
      seed: i + 40,
    })
  }
  // Mid-ring dense cluster for a solid 3D city read
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2 + 0.5
    const r = 5.2 + rand(i + 3) * 1.4
    const nearBot = slots.some((s) => {
      const dx = s.position[0] - Math.cos(a) * r
      const dz = s.position[2] - (Math.sin(a) * r - 0.8)
      return dx * dx + dz * dz < 3.2
    })
    if (nearBot) continue
    fillers.push({
      position: [Math.cos(a) * r, 0, Math.sin(a) * r - 0.8],
      height: 4.0 + rand(i + 15) * 4.8,
      width: 0.75 + rand(i + 8) * 0.9,
      seed: i + 60,
    })
  }
  return { slots, fillers }
}

export function CityScene({ bots, selectedId, onSelect }: Props) {
  return (
    <>
      <color attach="background" args={['#0a0320']} />
      <fog attach="fog" args={['#1a0740', 26, 70]} />
      <CityOrbitCamera />
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
      <ambientLight intensity={0.24} />
      <directionalLight position={[6, 18, 8]} intensity={0.5} color="#a8c8ff" />
      <pointLight position={[0, 6, 6]} intensity={1.7} color="#ffe9a0" distance={28} />
      <pointLight position={[-8, 5, -4]} intensity={1.15} color="#ff2a6d" distance={30} />
      <pointLight position={[8, 5, -4]} intensity={0.95} color="#2de2e6" distance={30} />
      <pointLight position={[0, 10, -8]} intensity={0.65} color="#b967ff" distance={40} />

      <PurpleHorizon />
      <Starfield count={1200} />
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
