/** Shape subset of paper-bots.pimp_desk.snapshot() used by the city UI. */

export type Money = number | null | undefined

export type Position = {
  what?: string
  title?: string
  detail?: string
  cost?: number | null
  side?: string
  ticker?: string
  team?: string
  game?: string
  prob?: number | null
  edge?: number | null
  bid?: number | null
  ask?: number | null
  fill?: number | null
  [key: string]: unknown
}

export type TradeOrHistory = {
  what?: string
  title?: string
  pnl?: number | null
  result?: string
  exit_reason?: string
  exit?: string
  when?: string
  closed_at?: string
  closed?: string
  team?: string
  game?: string
  ticker?: string
  [key: string]: unknown
}

export type BotPlans = {
  buy?: string[]
  sell?: string[]
  failsafes?: string[]
  exit_quality?: 'strong' | 'partial' | 'weak' | 'absent' | 'none' | string
  entry_gated?: boolean
  stake?: string
}

export type BotRow = {
  id: string
  name: string
  present?: boolean
  status?: string
  cash?: Money
  realized?: Money
  today?: Money
  open_count?: number
  open_risk?: Money
  paused?: boolean
  feed?: string | null
  why?: string
  skip?: string
  idle_copy?: string | null
  empty?: string
  last_check?: string
  central_check?: string
  next_run?: string
  warning?: string | null
  positions?: Position[]
  trades?: TradeOrHistory[]
  history?: TradeOrHistory[]
  would_have?: unknown[]
  has_state?: boolean
  blurb?: string
  plans?: BotPlans
  gates_hit?: string[]
}

export type Desk = {
  cash?: Money
  realized?: Money
  today?: Money
  open_risk?: Money
  open_count?: number
  last_check?: string
  central_check?: string
  next_check?: string
  trades_today?: number
  status_line?: string
  gate?: string
  week?: number
  week_wins?: number
  week_losses?: number
  goal?: number
  goal_bar?: number
  streak?: { kind?: string; n?: number; text?: string }
  equity?: { t?: string; v?: number }[]
  curve?: { t?: string; v?: number }[]
  spikes?: unknown[]
  pace_line?: string
  pace_loosened?: boolean
  paused_all?: boolean
  ops?: {
    entry_gate?: string
    entry_gated_bots?: string[]
    strong_exits?: string[]
    weak_exits?: string[]
  }
  chart?: {
    zone?: string
    default?: string
    ranges?: { id: string; label: string; start: string; end: string }[]
  }
}

export type Snapshot = {
  paper_only?: boolean
  banner?: string
  desk?: Desk
  bots?: BotRow[]
  limits?: Record<string, unknown>
  ok?: boolean
  error?: string
}

export type DataMode = 'live' | 'offline'

export type SnapshotState = {
  snap: Snapshot | null
  mode: DataMode
  error: string | null
  updatedAt: number | null
  loading: boolean
}
