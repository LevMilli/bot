import { useMemo } from 'react'
import type { BotRow, Desk } from '../types'
import { workersOnShift } from '../data/format'
import { GridFloor } from './GridFloor'
import {
  clearFromBackRoad,
  clearFromRail,
  hitsBackRoad,
  hitsRail,
  RAIL_R,
} from './plazaLayout'
import { PurpleHorizon, SkyEquityLine, Skyline, Starfield } from './Skyline'
import { Vault } from './Vault'
import { FillerTower, Tower } from './Tower'
import { CityOrbitCamera } from './CityControls'
import { BorderScreens } from './BorderScreens'

/** Trade towers sit inside the rail loop — well clear of ballast. */
export const RING_R = 7.15
/** Matches <Vault position={[0,0,5.2]} /> pad (~3.45r) plus building half-width. */
export const VAULT_XZ = { x: 0, z: 5.2 }
export const VAULT_CLEAR_R = 4.55
/** Trade towers must stay this far from vault center (clears BTC / pad collisions). */
const TOWER_VAULT_MIN = 6.15
/** Max radial distance from rail center so towers never sit on the tracks. */
const TOWER_RAIL_MAX = RAIL_R - 2.35
/** Keep fillers within this distance of a trade tower as “linked”. */
const TRADE_LINK_R = 3.2
/** Drop this fraction of unlinked fillers. */
const UNLINKED_DROP = 0.55
/** Minimum footprint separation between any two buildings. */
const BUILDING_GAP = 2.35

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

/** Clamp so vault-clear pushes never slam a tower onto the front rail arc. */
function clampInsideRail(x: number, z: number): [number, number] {
  const dx = x
  const dz = z + 1 // rail center z offset
  const d = Math.hypot(dx, dz)
  if (d <= TOWER_RAIL_MAX) return [x, z]
  if (d < 1e-6) return [0, -1 + TOWER_RAIL_MAX]
  const s = TOWER_RAIL_MAX / d
  return [dx * s, -1 + dz * s]
}

function settleFootprint(x0: number, z0: number, halfW: number): [number, number] {
  let x = x0
  let z = z0
  for (let k = 0; k < 6; k++) {
    ;[x, z] = clearFromVault(x, z, TOWER_VAULT_MIN)
    ;[x, z] = clampInsideRail(x, z)
    ;[x, z] = clearFromRail(x, z, halfW)
    ;[x, z] = clearFromBackRoad(x, z, halfW)
    ;[x, z] = clampInsideRail(x, z)
  }
  return [x, z]
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

function overlapsAny(
  x: number,
  z: number,
  halfW: number,
  others: { x: number; z: number; halfW: number }[],
) {
  return others.some((o) => {
    const min = BUILDING_GAP + halfW + o.halfW
    const dx = x - o.x
    const dz = z - o.z
    return dx * dx + dz * dz < min * min
  })
}

/** Same plaza layout the city camera uses, so the office window matches the live city. */
export function layoutCity(bots: BotRow[]): { slots: CitySlot[]; fillers: FillerSlot[] } {
  const n = Math.max(bots.length, 5)
  const placed: { x: number; z: number; halfW: number }[] = []

  const slots = bots.map((bot, i) => {
    // Arc inside the railroad — vault toward camera, BTC kept off the front rail.
    const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + 0.18
    let x = Math.cos(a) * RING_R
    let z = Math.sin(a) * RING_R - 0.4
    const halfW = 1.05
    // Extra vault clearance for BTC, then clamp so it can't ride the tracks.
    const vaultMin =
      bot.id === 'btc15m' || /btc/i.test(bot.name || '') ? TOWER_VAULT_MIN + 0.85 : TOWER_VAULT_MIN
    ;[x, z] = clearFromVault(x, z, vaultMin)
    ;[x, z] = settleFootprint(x, z, halfW)

    // Separate from already-placed trade towers.
    for (let t = 0; t < 5; t++) {
      if (!overlapsAny(x, z, halfW, placed)) break
      const bump = 0.55 + t * 0.35
      const d = Math.hypot(x, z + 1) || 1
      x = (x / d) * Math.min(d + bump, TOWER_RAIL_MAX)
      z = -1 + ((z + 1) / d) * Math.min(d + bump, TOWER_RAIL_MAX)
      ;[x, z] = settleFootprint(x, z, halfW)
    }

    placed.push({ x, z, halfW })
    return { bot, index: i, position: [x, 0, z] as [number, number, number] }
  })

  const candidates: FillerSlot[] = []

  const tryFiller = (x0: number, z0: number, width: number, height: number, seed: number) => {
    const halfW = width * 0.55
    let x = x0
    let z = z0
    ;[x, z] = settleFootprint(x, z, halfW)
    if (hitsVault(x, z, halfW)) return
    if (hitsRail(x, z, halfW)) return
    if (hitsBackRoad(x, z, halfW)) return
    if (overlapsAny(x, z, halfW, placed)) return
    candidates.push({ position: [x, 0, z], height, width, seed })
    placed.push({ x, z, halfW })
  }

  // Inner cluster — behind vault, inside rail.
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2 + 0.55
    const r = 2.6 + rand(i + 2) * 1.2
    tryFiller(
      Math.cos(a) * r,
      Math.sin(a) * r - 0.6,
      0.8 + rand(i + 4) * 0.75,
      3.4 + rand(i + 9) * 4.8,
      i + 20,
    )
  }

  // Outer ring — outside the railroad (beyond ballast).
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2 + 0.08
    const r = RAIL_R + 2.6 + rand(i + 1) * 1.4
    const x = Math.cos(a) * r
    const z = Math.sin(a) * r - 1
    // Skip footprints that would land on the back avenue.
    if (hitsBackRoad(x, z, 1.1)) continue
    tryFiller(x, z, 0.7 + rand(i + 6) * 1.0, 2.8 + rand(i + 11) * 5.2, i + 40)
  }

  // Mid-ring inside rail.
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2 + 0.7
    const r = 4.6 + rand(i + 3) * 1.1
    tryFiller(
      Math.cos(a) * r,
      Math.sin(a) * r - 0.8,
      0.75 + rand(i + 8) * 0.8,
      4.0 + rand(i + 15) * 4.2,
      i + 60,
    )
  }

  const linked: FillerSlot[] = []
  const unlinked: FillerSlot[] = []
  for (const f of candidates) {
    const [x, , z] = f.position
    if (nearTrade(x, z, slots)) linked.push(f)
    else unlinked.push(f)
  }

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
      <ambientLight intensity={0.55} />
      <directionalLight position={[6, 18, 8]} intensity={0.75} color="#a8c8ff" />
      <pointLight position={[0, 8, 3]} intensity={1.4} color="#ffe9a0" distance={30} />

      <PurpleHorizon />
      <Starfield count={160} />
      <GridFloor />
      <BorderScreens bots={bots} />
      <Skyline z={-46} width={52} />
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
