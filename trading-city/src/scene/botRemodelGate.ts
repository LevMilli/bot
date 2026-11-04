/**
 * Purple industrial bot remodel rollout gate.
 *
 * User approved city-wide: cars, tellers, hallway, and office desks all use
 * IndustrialBotFigure via CityBotFigure.
 */
export const BOT_REMODEL_PREVIEW_OFFICE = true
export const BOT_REMODEL_APPROVED = true

export function shouldUseIndustrialBot(context: 'office' | 'city' | 'bank' | 'hall') {
  if (BOT_REMODEL_APPROVED) return true
  return BOT_REMODEL_PREVIEW_OFFICE && context === 'office'
}
