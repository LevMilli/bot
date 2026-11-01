import { useMemo } from 'react'
import type { BotRow, Desk } from '../types'
import { workersOnShift } from '../data/format'
import { NeonBloom } from './Effects'
import { GridFloor } from './GridFloor'
import { PurpleHorizon, SkyEquityLine, Skyline, Starfield } from './Skyline'
import { Vault } from './Vault'
import { FillerTower, Tower } from './Tower'
import { CityOrbitCamera } from './CityControls'

export const RING_R = 8.4
/** Matches <Vault position={[0,0,5.2]} /> pad (~3.45r) plus building half-width. */
export const VAULT_XZ = { x: 0, z: 5.2 }
export const VAULT_CLEAR_R = 4.55
/** Trade towers must stay this far from vault center (clears BTC / pad collisions). */
const TOWER_VAULT_MIN = 6.4
/** Keep fillers within this distance of a trade tower as “linked”. */
const TRADE_LINK_R = 3.4
/** Drop this fraction of unlinked fillers (15–20%). */
const UNLINKED_DROP = 0.18

type Props = {
  bots: BotRow[]
  desk?: Desk
  selectedId: string | null
  onSelect: (id: string) => void
  onOpenVault?: () => void
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

function hitsVault(x: number, z: number, halfW: number) {
  const dx = x - VAULT_XZ.x
  const dz = z - VAULT_XZ.z
  const clear = VAULT_CLEAR_R + halfW
  return dx * dx + dz * dz < clear * clear
}

/** Push a point radially away from the vault until it clears minDist. */
function clearFromVault(x: number, z: number, minDist = TOWER_VAULT_MIN): [number, number] {
  const dx = x - VAULT_XZ.x
  const dz = z - VAULT_XZ.z
  const d = Math.hypot(dx, dz)
  if (d >= minDist) return [x, z]
  if (d < 1e-6) return [x, z - minDist]
  const s = minDist / d
  return [VAULT_XZ.x + dx * s, VAULT_XZ.z + dz * s]
}

function nearTrade(
  x: number,
  z: number,
  slots: CitySlot[],
  linkR = TRADE_LINK_R,
) {
  const r2 = linkR * linkR
  return slots.some((s) => {
    const dx = s.position[0] - x
    const dz = s.position[2] - z
    return dx * dx + dz * dz < r2
  })
}

/** Same plaza layout the city camera uses, so the office window matches the live city. */
export function layoutCity(bots: BotRow[]): { slots: CitySlot[]; fillers: FillerSlot[] } {
  const n = Math.max(bots.length, 5)
  const slots = bots.map((bot, i) => {
    // Vault sits toward camera; towers arc behind / beside it.
    // BTC / vault-facing slots get pushed out so beams never clip the pad.
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.12
    let x = Math.cos(a) * RING_R
    let z = Math.sin(a) * RING_R - 0.8
    ;[x, z] = clearFromVault(x, z, TOWER_VAULT_MIN)
    // Extra nudge for known vault-side bots (btc15m often lands on the pad arc).
    if (bot.id === 'btc15m' || /btc/i.test(bot.name || '')) {
      ;[x, z] = clearFromVault(x, z, TOWER_VAULT_MIN + 1.1)
    }
    return { bot, index: i, position: [x, 0, z] as [number, number, number] }
  })

  const candidates: FillerSlot[] = []

  // Inner cluster — keep behind the vault (not on the pad toward camera).
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2 + 0.35
    const r = 2.8 + rand(i + 2) * 1.5
    const x = Math.cos(a) * r
    const z = Math.sin(a) * r - 0.6
    const width = 0.8 + rand(i + 4) * 0.85
    if (hitsVault(x, z, width * 0.55)) continue
    candidates.push({
      position: [x, 0, z],
      height: 3.4 + rand(i + 9) * 5.2,
      width,
      seed: i + 20,
    })
  }

  // Outer ring around the plaza rail
  for (let i = 0; i < 20; i++) {
    const a = (i / 20) * Math.PI * 2 + 0.08
    const r = 9.2 + rand(i + 1) * 1.8
    const x = Math.cos(a) * r
    const z = Math.sin(a) * r - 1
    const width = 0.65 + rand(i + 6) * 1.2
    if (hitsVault(x, z, width * 0.55)) continue
    candidates.push({
      position: [x, 0, z],
      height: 2.8 + rand(i + 11) * 5.8,
      width,
      seed: i + 40,
    })
  }

  // Mid-ring density
  for (let i = 0; i < 11; i++) {
    const a = (i / 11) * Math.PI * 2 + 0.5
    const r = 5.2 + rand(i + 3) * 1.4
    const x = Math.cos(a) * r
    const z = Math.sin(a) * r - 0.8
    const width = 0.75 + rand(i + 8) * 0.9
    if (hitsVault(x, z, width * 0.55)) continue
    candidates.push({
      position: [x, 0, z],
      height: 4.0 + rand(i + 15) * 4.8,
      width,
      seed: i + 60,
    })
  }

  const linked: FillerSlot[] = []
  const unlinked: FillerSlot[] = []
  for (const f of candidates) {
    const [x, , z] = f.position
    if (nearTrade(x, z, slots)) linked.push(f)
    else unlinked.push(f)
  }

  // Drop ~18% of fillers that aren’t near a trade tower.
  const keepUnlinked = unlinked.filter((_, i) => rand(i + 77) > UNLINKED_DROP)

  return { slots, fillers: [...linked, ...keepUnlinked] }
}

export function CityScene({ bots, desk, selectedId, onSelect, onOpenVault }: Props) {
  return (
    <>
      <color attach="background" args={['#0a0320']} />
      <fog attach="fog" args={['#1a0740', 26, 70]} />
      <CityOrbitCamera />
      <CityContents
        bots={bots}
        desk={desk}
        selectedId={selectedId}
        onSelect={onSelect}
        onOpenVault={onOpenVault}
      />
      <NeonBloom />
    </>
  )
}

/** Plaza, towers, vault, and sky for the city camera. The office window uses its own street view. */
export function CityContents({
  bots,
  desk,
  selectedId,
  onSelect,
  onOpenVault,
}: {
  bots: BotRow[]
  desk?: Desk
  selectedId: string | null
  onSelect: (id: string) => void
  onOpenVault?: () => void
}) {
  const { slots, fillers } = useMemo(() => layoutCity(bots), [bots])
  const workers = workersOnShift(bots)
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
      <Vault desk={desk} workers={workers} onOpen={onOpenVault} />

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
