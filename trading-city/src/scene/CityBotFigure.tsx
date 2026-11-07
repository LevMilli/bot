import { BotFigure } from './BotFigure'
import { IndustrialBotFigure } from './IndustrialBotFigure'
import { shouldUseIndustrialBot } from './botRemodelGate'
import type { BotPose } from '../data/botPose'

type Context = 'office' | 'city' | 'bank' | 'hall'

/** Picks classic vs purple industrial bot from the remodel gate. */
export function CityBotFigure({
  context,
  pose = 'waiting',
  seated = true,
  deskWork = false,
  seed = 0,
  unitMark,
  /** Force low-poly silhouette (far tellers / background patrons). */
  lite,
}: {
  context: Context
  pose?: BotPose
  seated?: boolean
  deskWork?: boolean
  seed?: number
  unitMark?: string
  lite?: boolean
}) {
  if (shouldUseIndustrialBot(context)) {
    return (
      <IndustrialBotFigure
        pose={pose}
        seated={seated}
        deskWork={deskWork}
        seed={seed}
        unitMark={unitMark}
        /** Plaza cars always lite; callers can also request lite for distant bank extras. */
        lite={lite ?? context === 'city'}
        /** Bank window staff get trust-hall cyan/brass teller kit. */
        variant={context === 'bank' ? 'teller' : 'default'}
      />
    )
  }
  return <BotFigure pose={pose} seated={seated} deskWork={deskWork} seed={seed} />
}
