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

export type BotShadow = {
  active?: boolean
  variant_id?: string
  cash?: number
  expectancy?: number | null
  n?: number
  promote_ready?: boolean
  params?: Record<string, unknown>
  open_count?: number
  shadow_only?: boolean
  bot?: string
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
  skip_board?: { code?: string; n?: number }[]
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
  expectancy?: number | null
  expectancy_n?: number
  expectancy_hit_rate?: number | null
  expectancy_window?: string
  avg_win?: number | null
  avg_loss?: number | null
  capital_weight?: number
  starved?: boolean
  starve_reason?: string
  starve_factor?: number
  risk_factors_open?: string[]
  shadow?: BotShadow | null
  venue_min_edge?: number | null
  sizing_mode?: 'curve' | 'kelly_lite' | 'fixed' | 'none' | string
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
  capital?: {
    method?: string
    weights?: Record<string, number>
  }
  shadow_leaderboard?: BotShadow[]
  ops?: {
    entry_gate?: string
    entry_gated_bots?: string[]
    strong_exits?: string[]
    weak_exits?: string[]
    roi_ok?: boolean
    roi_version?: number
    correlation_pressure?: string[]
    starved_bots?: string[]
    shadow_count?: number
    fill_tax?: number
    gate_a_ready_bots?: string[]
  }
  more?: {
    skip_leaderboard?: {
      top?: { code?: string; n?: number; stable?: string }[]
      stable_top?: { code?: string; n?: number }[]
      taxonomy?: string[]
      weekend_n?: number
      weekday_n?: number
      note?: string
      by_bot?: Record<string, Record<string, number>>
    }
    tower_budgets?: Record<string, number>
    sticky_count?: number
  }
  top25?: {
    city_vault?: {
      show_skip_board?: boolean
      show_budget_bars?: boolean
      show_adapt_dial?: boolean
      fill_tax_education?: boolean
      guest_readonly_query?: string
    }
    gate_b?: { any_ready?: boolean; bots?: { bot?: string; ready?: boolean }[] }
    doctor?: { ok?: boolean; hint?: string }
    dual_control?: { armed?: boolean; status?: string }
  }
  gate_a?: {
    any_ready?: boolean
    fill_tax?: number
    note?: string
  }
  gate_b?: {
    any_ready?: boolean
    note?: string
  }
  sports_tip?: {
    paper_only?: boolean
    active?: boolean
    band?: number | null
    n_pre?: number
    n_tip?: number
    nearest_eta_min?: number | null
    sample?: string
    force_sec?: number
    window_min?: number
    note?: string
  }
  master?: {
    paper_only?: boolean
    version?: number
    stopbleed?: {
      stop_exits?: number
      model_flip_exits?: number
      trail_exits?: number
      red_day_locked?: boolean
      expand_volume?: boolean
      stopbleed_pnl?: number
      today?: number | null
      note?: string
    }
    sports_tip?: Desk['sports_tip']
    towers?: unknown[]
    note?: string
  }
  chart?: {
    zone?: string
    default?: string
    ranges?: { id: string; label: string; start: string; end: string }[]
  }
  /** desk_adapt summary + vault dial counters from snapshot */
  adapt?: {
    paper_only?: boolean
    version?: number
    series_15m?: string[]
    by_bot?: Record<
      string,
      Record<string, unknown> & { safe?: number; big?: number; obs?: number }
    >
    recent_vol?: unknown[]
    rules?: Record<string, unknown>
    error?: string
  }
}

export type RoiCompliance = {
  bot?: string
  ok?: boolean
  exit_quality?: string
  target_exit_quality?: string
  entry_gated?: boolean
  waivers?: string[]
  gaps?: string[]
}

export type RoiSystem = {
  name?: string
  version?: number
  paper_only?: boolean
  banner?: string
  ok?: boolean
  rules?: { id?: string; text?: string }[]
  risk?: Record<string, unknown>
  exit_ladder?: Record<string, string>
  waivers?: Record<string, string[]>
  compliance?: RoiCompliance[]
}

export type TimerHealth = {
  alive?: boolean
  detail?: string
  age?: number | null
  alert?: string
}

export type Snapshot = {
  paper_only?: boolean
  banner?: string
  desk?: Desk
  bots?: BotRow[]
  limits?: Record<string, unknown>
  roi_system?: RoiSystem
  health?: TimerHealth
  timer?: string
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
