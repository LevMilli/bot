/**
 * FloorMap schema (APEX-CITY 1000-step plan E4).
 * Routes: #/plaza | #/bank | #/floor/:id | #/office/:botId | #/boss
 * Snapshot remains the single data path — this only places bots in space.
 */

export type FloorId = '0' | '1' | '2' | '3' | '4' | '5' | '6'

export type FloorOffice = {
  officeId: string
  botId: string | null
  label: string
  boss?: boolean
  helper?: boolean
}

export type FloorDef = {
  id: FloorId
  name: string
  wing: string
  offices: FloorOffice[]
}

/** Campus floors — stub until full walk scenes land. */
export const FLOORS: FloorDef[] = [
  {
    id: '0',
    name: 'Vault hall',
    wing: 'Lobby',
    offices: [{ officeId: 'vault', botId: null, label: 'APEX-CITY TRUST' }],
  },
  {
    id: '1',
    name: 'Trading wing',
    wing: 'Spine hall',
    offices: [
      { officeId: 'sports-gap', botId: 'sports-gap', label: 'Sports gap' },
      { officeId: 'kalshi-sp', botId: 'kalshi-sp', label: 'Kalshi S&P' },
      { officeId: 'btc15m', botId: 'btc15m', label: 'BTC 15m' },
      { officeId: 'commodity-15m', botId: 'commodity-15m', label: 'Commodity 15m' },
      { officeId: 'memecoin', botId: 'memecoin', label: 'Memecoin' },
      { officeId: 'coinbase-spot', botId: 'coinbase-spot', label: 'Coinbase spot' },
      { officeId: 'btc-carry', botId: 'btc-carry', label: 'BTC carry' },
      { officeId: 'boss', botId: 'kalshi-sized', label: 'Boss · Sized Kalshi', boss: true },
    ],
  },
  {
    id: '2',
    name: 'Crypto & Commodity',
    wing: 'Microstructure',
    offices: [
      { officeId: 'btc15m', botId: 'btc15m', label: 'BTC 15m' },
      { officeId: 'coinbase-spot', botId: 'coinbase-spot', label: 'Coinbase spot' },
      { officeId: 'btc-carry', botId: 'btc-carry', label: 'BTC carry' },
      { officeId: 'commodity-15m', botId: 'commodity-15m', label: 'Commodity 15m' },
    ],
  },
  {
    id: '3',
    name: 'Speculative',
    wing: 'Meme',
    offices: [{ officeId: 'memecoin', botId: 'memecoin', label: 'Memecoin' }],
  },
  {
    id: '4',
    name: 'Research helpers',
    wing: 'Research',
    offices: [
      { officeId: 'calendar-helper', botId: null, label: 'Calendar cache', helper: true },
      { officeId: 'tape-helper', botId: null, label: 'Tape scout', helper: true },
      { officeId: 'sports-sharp-lag', botId: 'sports-sharp-lag', label: 'Sports sharp lag' },
      { officeId: 'fed-watch', botId: 'fed-watch', label: 'Fed Watch' },
    ],
  },
  {
    id: '5',
    name: 'Risk & Compliance',
    wing: 'Risk',
    offices: [{ officeId: 'risk', botId: null, label: 'Risk sentinel', helper: true }],
  },
  {
    id: '6',
    name: 'Boss suite',
    wing: 'Executive',
    offices: [{ officeId: 'boss', botId: null, label: 'War Room', boss: true }],
  },
]

export function floorForBot(botId: string): FloorDef | null {
  return FLOORS.find((f) => f.offices.some((o) => o.botId === botId)) || null
}

export function parseCityHash(hash: string): {
  view: 'plaza' | 'bank' | 'floor' | 'office' | 'boss'
  floorId?: FloorId
  botId?: string
} {
  const raw = (hash || '').replace(/^#\/?/, '').trim()
  if (!raw || raw === 'plaza' || raw === 'city') return { view: 'plaza' }
  if (raw === 'bank' || raw === 'vault') return { view: 'bank' }
  if (raw === 'boss') return { view: 'boss' }
  const floor = raw.match(/^floor\/([0-6])$/)
  if (floor) return { view: 'floor', floorId: floor[1] as FloorId }
  const office = raw.match(/^office\/([a-z0-9-]+)$/i)
  if (office) return { view: 'office', botId: office[1] }
  return { view: 'plaza' }
}
