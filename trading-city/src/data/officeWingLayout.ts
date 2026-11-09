/**
 * Trading-wing office layouts for APEX-CITY.
 * Plan A (linear spine) is the live 3D model. B/C are documented alternates.
 */

export type WingLayoutId = 'spine' | 'tee' | 'courtyard'

export type WingRoom = {
  id: string
  botId: string
  label: string
  boss?: boolean
  /** Room center in wing space (hallway along +X). */
  position: [number, number, number]
  /** Yaw so the door faces the hallway. */
  yaw: number
  side: 'left' | 'right' | 'end'
}

/** Worker desks + boss suite. Coinbase spot is the shadow tower on the crypto side. */
export const WORKER_BOT_IDS = [
  'sports-gap',
  'kalshi-sp',
  'btc15m',
  'commodity-15m',
  'memecoin',
  'coinbase-spot',
  'btc-carry',
] as const

export const BOSS_BOT_ID = 'kalshi-sized'

/**
 * Plan A — linear spine (shipping).
 * Room centers sit so the open doorway flush-meets the hallway edge
 * (ROOM_HALF_D 4 + hall half-width 1.55 ≈ 5.55).
 */
export const SPINE_ROOMS: WingRoom[] = [
  {
    id: 'sports-gap',
    botId: 'sports-gap',
    label: 'Sports gap',
    position: [5.2, 0, -5.55],
    yaw: 0,
    side: 'left',
  },
  {
    id: 'commodity-15m',
    botId: 'commodity-15m',
    label: 'Commodity 15m',
    position: [5.2, 0, 5.55],
    yaw: Math.PI,
    side: 'right',
  },
  {
    id: 'kalshi-sp',
    botId: 'kalshi-sp',
    label: 'Kalshi S&P',
    position: [13.2, 0, -5.55],
    yaw: 0,
    side: 'left',
  },
  {
    id: 'memecoin',
    botId: 'memecoin',
    label: 'Memecoin',
    position: [13.2, 0, 5.55],
    yaw: Math.PI,
    side: 'right',
  },
  {
    id: 'btc15m',
    botId: 'btc15m',
    label: 'BTC 15m',
    position: [21.2, 0, -5.55],
    yaw: 0,
    side: 'left',
  },
  {
    id: 'coinbase-spot',
    botId: 'coinbase-spot',
    label: 'Coinbase spot',
    position: [21.2, 0, 5.55],
    yaw: Math.PI,
    side: 'right',
  },
  {
    id: 'btc-carry',
    botId: 'btc-carry',
    label: 'BTC carry',
    position: [29.2, 0, -5.55],
    yaw: 0,
    side: 'left',
  },
  {
    id: 'boss',
    botId: BOSS_BOT_ID,
    label: 'Boss · Sized Kalshi',
    boss: true,
    // Door at local +Z faces −X into the hall after yaw −90°.
    position: [43.2, 0, 0],
    yaw: -Math.PI / 2,
    side: 'end',
  },
]

export const WING_LAYOUTS: Record<
  WingLayoutId,
  { name: string; blurb: string; rooms: WingRoom[] }
> = {
  spine: {
    name: 'Linear spine',
    blurb: 'Main hallway with workers on both sides and the boss suite at the far end.',
    rooms: SPINE_ROOMS,
  },
  tee: {
    name: 'T-hall',
    blurb: 'Stem of three workers; crossbar holds two workers and a center boss suite.',
    rooms: [
      { id: 'sports-gap', botId: 'sports-gap', label: 'Sports gap', position: [4, 0, 0], yaw: -Math.PI / 2, side: 'left' },
      { id: 'kalshi-sp', botId: 'kalshi-sp', label: 'Kalshi S&P', position: [10, 0, 0], yaw: -Math.PI / 2, side: 'left' },
      { id: 'btc15m', botId: 'btc15m', label: 'BTC 15m', position: [16, 0, 0], yaw: -Math.PI / 2, side: 'left' },
      { id: 'commodity-15m', botId: 'commodity-15m', label: 'Commodity 15m', position: [22, 0, -6], yaw: 0, side: 'left' },
      { id: 'memecoin', botId: 'memecoin', label: 'Memecoin', position: [22, 0, 6], yaw: Math.PI, side: 'right' },
      { id: 'coinbase-spot', botId: 'coinbase-spot', label: 'Coinbase spot', position: [16, 0, 6], yaw: Math.PI, side: 'right' },
      { id: 'btc-carry', botId: 'btc-carry', label: 'BTC carry', position: [16, 0, -6], yaw: 0, side: 'left' },
      {
        id: 'boss',
        botId: BOSS_BOT_ID,
        label: 'Boss · Sized Kalshi',
        boss: true,
        position: [22, 0, 0],
        yaw: Math.PI,
        side: 'end',
      },
    ],
  },
  courtyard: {
    name: 'U-courtyard',
    blurb: 'Workers wrap a short court; boss closes the far open end.',
    rooms: [
      { id: 'sports-gap', botId: 'sports-gap', label: 'Sports gap', position: [4, 0, -6], yaw: 0, side: 'left' },
      { id: 'kalshi-sp', botId: 'kalshi-sp', label: 'Kalshi S&P', position: [10, 0, -6], yaw: 0, side: 'left' },
      { id: 'btc15m', botId: 'btc15m', label: 'BTC 15m', position: [16, 0, -6], yaw: 0, side: 'left' },
      { id: 'commodity-15m', botId: 'commodity-15m', label: 'Commodity 15m', position: [4, 0, 6], yaw: Math.PI, side: 'right' },
      { id: 'memecoin', botId: 'memecoin', label: 'Memecoin', position: [10, 0, 6], yaw: Math.PI, side: 'right' },
      { id: 'coinbase-spot', botId: 'coinbase-spot', label: 'Coinbase spot', position: [16, 0, 6], yaw: Math.PI, side: 'right' },
      { id: 'btc-carry', botId: 'btc-carry', label: 'BTC carry', position: [16, 0, -6], yaw: 0, side: 'left' },
      {
        id: 'boss',
        botId: BOSS_BOT_ID,
        label: 'Boss · Sized Kalshi',
        boss: true,
        position: [18, 0, 0],
        yaw: -Math.PI / 2,
        side: 'end',
      },
    ],
  },
}

export const ACTIVE_WING_LAYOUT: WingLayoutId = 'spine'

export function activeWingRooms(): WingRoom[] {
  return WING_LAYOUTS[ACTIVE_WING_LAYOUT].rooms
}

export function roomForBot(botId: string): WingRoom | null {
  return activeWingRooms().find((r) => r.botId === botId) || null
}
