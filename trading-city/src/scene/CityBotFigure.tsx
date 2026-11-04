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
}: {
  context: Context
  pose?: BotPose
  seated?: boolean
  deskWork?: boolean
  seed?: number
  unitMark?: string
}) {
  if (shouldUseIndustrialBot(context)) {
    return (
      <IndustrialBotFigure
        pose={pose}
        seated={seated}
        deskWork={deskWork}
        seed={seed}
        unitMark={unitMark}
        /** Tiny plaza car riders — silhouette only to keep WebGL light. */
        lite={context === 'city'}
      />
    )
  }
  return <BotFigure pose={pose} seated={seated} deskWork={deskWork} seed={seed} />
}
