import { useMemo } from 'react'
import type { BotRow, Desk } from '../types'
import { layoutCity } from './CityScene'
import { GridFloor } from './GridFloor'
import { PurpleHorizon, SkyEquityLine, Skyline, Starfield } from './Skyline'
import { FillerTower, Tower } from './Tower'
import { Vault } from './Vault'

/**
 * The live plaza, placed just outside the office glass.
 * Same towers, vault, rail, and avenue as the city camera — real meshes,
 * so looking around the office shows depth instead of a flat picture.
 * Offset keeps the railroad and towers outside the room.
 * Border plaza screens stay on the outdoor CityScene — not behind the glass —
 * so the office stays clear of those vertical tower bars.
 */
export function StreetCity({ bots, desk }: { bots: BotRow[]; desk?: Desk }) {
  const { slots, fillers } = useMemo(() => layoutCity(bots), [bots])

  return (
    <group position={[3.2, 0, -16]}>
      <PurpleHorizon />
      <Starfield count={320} />
      {/* No park pads here — one of them crosses the glass and lands on the office floor. */}
      <GridFloor parks={false} />
      {/* No BorderScreens behind office glass — keeps the suite clear of tower bars. */}
      <Skyline z={-48} width={72} />
      <Skyline z={-56} width={88} />
      <SkyEquityLine />
      <Vault lights={false} showHolo={false} desk={desk} />
      {fillers.map((filler, i) => (
        <FillerTower key={`win-${i}`} {...filler} />
      ))}
      {slots.map(({ bot, index, position }) => (
        <Tower
          key={bot.id}
          bot={bot}
          index={index}
          position={position}
          selected={false}
          onSelect={() => {}}
          vista
        />
      ))}
    </group>
  )
}
