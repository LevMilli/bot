/**
 * Purple industrial bot remodel rollout gate.
 *
 * PREVIEW: office desk bots only (`BOT_REMODEL_PREVIEW_OFFICE`).
 * FULL CITY: flip `BOT_REMODEL_APPROVED` after user sign-off — cars, tellers, hallway.
 */
export const BOT_REMODEL_PREVIEW_OFFICE = true
export const BOT_REMODEL_APPROVED = false

export function shouldUseIndustrialBot(context: 'office' | 'city' | 'bank' | 'hall') {
  if (BOT_REMODEL_APPROVED) return true
  return BOT_REMODEL_PREVIEW_OFFICE && context === 'office'
}
