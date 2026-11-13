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

/** Lifetime paper record. Counts books cleared by the midnight refill or a staff reset. */
export type Lifetime = {
  realized?: Money
  banked?: Money
  current?: Money
  trades?: number
  wins?: number
  losses?: number
  max_drawdown?: Money
  resets?: number
  wiped_losses?: Money
  complete?: boolean
  note?: string
  error?: string
  /** Same trades with worse fills: 1¢/2¢ per contract (Kalshi) or 0.10%/0.25% each way (coins). */
  worse?: {
    kind?: string
    label_1?: string
    label_2?: string
    realized_1?: Money
    realized_2?: Money
    measured?: number
    trades?: number
    note?: string
  } | null
}

export type BotRow = {
  id: string
  name: string
  present?: boolean
  status?: string
  cash?: Money
  realized?: Money
  today?: Money
  /** Shadow books spend no desk cash and are not added to the vault. */
  shadow_only?: boolean
  open_count?: number
  /** Wall Street floor headcount. Staff on one book, not extra strategies. */
  traders?: number
  /** Wall Street desks. Staff jobs on the one book. They do not buy. */
  departments?: { id: string; name: string; seats: number; job: string }[]
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
  memory_line?: string
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
  lifetime?: Lifetime | null
  /** Plain-words city card from paper-bots/city_card.py. Read only. */
  card?: CityCard | null
}

export type CityTradeLine = { what?: string; pnl?: number | null }

export type CityCard = {
  district?: string
  every_sec?: number | null
  scan_times?: string[]
  next_check_in_sec?: number | null
  today?: {
    settled?: number
    wins?: number
    losses?: number
    flat?: number
    pnl?: number
    fees?: number
    early_sales?: number
    early_pnl?: number
    held?: number
    held_pnl?: number
    best?: CityTradeLine | null
    worst?: CityTradeLine | null
  }
  trades_today?: number
  settled_total?: number
  progress?: { have?: number; need?: number; counts?: boolean; note?: string } | null
  why_no_trade?: string
  learning_skip?: string
  error?: string
  floor?: number | null
}

export type CityBannerFacts = {
  real_money?: string
  today?: number
  lifetime_realized?: number | null
  lifetime_wins?: number
  lifetime_losses?: number
  stop?: number
  stop_left?: number
  open_count?: number
  max_open?: number
  open_risk?: number
  max_open_risk?: number
  halted?: boolean
  halt_reason?: string
  gate?: string
  districts?: { id: string; sign: string }[]
  results_needed?: number
  error?: string
}

export type Desk = {
  /** City banner numbers from paper-bots/city_card.py. */
  city?: CityBannerFacts
  cash?: Money
  realized?: Money
  today?: Money
  /** Desk towers in the vault, and shadow towers kept on their own books. */
  bankroll?: {
    paper_only?: boolean
    towers?: string[]
    connected?: string[]
    missing?: string[]
    cash?: number | null
    realized?: number | null
    today?: number
    shadow_towers?: string[]
    shadow_cash?: number | null
    shadow_realized?: number | null
    shadow_today?: number
    note?: string
  }
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
  lifetime?: Lifetime
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
  tip_radar?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    t5?: number
    t15?: number
    t180?: number
    label?: string
    note?: string
    error?: string
  }
  empty_card?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    p50_s?: number | null
    pass?: boolean
    label?: string
    note?: string
    error?: string
  }
  near_miss?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    promote_ready?: boolean
    auto_promote?: boolean
    label?: string
    note?: string
    error?: string
  }
  skip_regret?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    green_twin?: boolean
    loosen_soft_gates?: boolean
    label?: string
    note?: string
    error?: string
  }
  hard_stop?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    promote_ready?: boolean
    auto_promote?: boolean
    live?: boolean
    label?: string
    note?: string
    error?: string
  }
  injury_wire?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    inbox_n?: number
    label?: string
    note?: string
    error?: string
  }
  eia_scout?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    next_eta_hours?: number | null
    label?: string
    note?: string
    error?: string
  }
  calendar_scanner?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    label?: string
    note?: string
    error?: string
  }
  eia_blackout?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    blocked?: boolean
    window_min?: number
    label?: string
    note?: string
    error?: string
  }
  living_compact?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    label?: string
    parts?: string[]
    ritual_ok?: boolean | null
    ritual_label?: string
    doctor_fresh?: boolean | null
    doctor_label?: string
    quiet_age?: string
    quiet_age_h?: number | null
    quiet_age_label?: string
    sunday_quiet_age?: string
    sunday_quiet_age_label?: string
    masters_sunday_label?: string
    masters_sunday_quiet?: string
    expand_sunday_quiet?: string
    floors_sunday_quiet?: string
    ruin_sunday_quiet?: string
    swarm_sunday_quiet?: string
    hill_sunday_quiet?: string
    gaps_sunday_quiet?: string
    quiet_label?: string
    note?: string
    error?: string
  }
  digest_inventory?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    present_n?: number
    expected_n?: number
    missing_n?: number
    ratio?: number | null
    pass?: boolean
    label?: string
    note?: string
    error?: string
  }
  hillclimb_chip?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    active_name?: string | null
    label?: string
    note?: string
    error?: string
  }
  dual_control_gaps?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    page?: boolean
    gaps_n?: number
    label?: string
    note?: string
    error?: string
  }
  living_ai?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    raise_phi_n?: number
    raise_phi_tickets?: string[]
    auto_write_phi?: boolean
    label?: string
    note?: string
    error?: string
  }
  feature_quiet?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    quiet?: boolean
    age_hours?: number | null
    label?: string
    alert?: string
    note?: string
    error?: string
  }
  feature_quiet_pager?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    page?: boolean
    auto_page?: boolean
    label?: string
    copy?: string
    note?: string
    error?: string
  }
  firm_queue?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    offers_n?: number
    accepted_n?: number
    deferred_n?: number
    remaining_risk?: number | null
    label?: string
    note?: string
    error?: string
  }
  helper_gate_a?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    ready_n?: number
    helpers_n?: number
    armed_n?: number
    auto_promote?: boolean
    places_orders?: boolean
    label?: string
    note?: string
    error?: string
  }
  skip_taxonomy?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    top_code?: string
    top_n?: number
    label?: string
    note?: string
    error?: string
  }
  distance_clerk?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    empty_card_pass?: boolean
    firm_offers_n?: number
    label?: string
    note?: string
    error?: string
  }
  quant_clerk?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    fit_pass?: boolean
    fit_rate?: number | null
    auto_write?: boolean
    label?: string
    note?: string
    error?: string
  }
  bookkeeper?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    fee_ledger_complete?: boolean
    eligible_completions_today?: number
    label?: string
    note?: string
    error?: string
  }
  reporter?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    present?: boolean
    auto_publish?: boolean
    label?: string
    note?: string
    error?: string
  }
  sunday_packet?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    present?: boolean
    auto_publish?: boolean
    chicago_today?: string
    scorecard_present?: boolean
    ritual_ok?: boolean | null
    quiet_age?: string
    quiet_age_label?: string
    ritual?: {
      ritual_ok?: boolean | null
      exit_ok?: boolean | null
      make?: string
      auto_publish?: boolean
    }
    label?: string
    note?: string
    error?: string
  }
  empty_card_bee?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    breaches?: number
    label?: string
    note?: string
    error?: string
  }
  near_miss_clerk?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    promote_ready?: boolean
    auto_promote?: boolean
    label?: string
    note?: string
    error?: string
  }
  hard_stop_clerk?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    promote_ready?: boolean
    auto_promote?: boolean
    live?: boolean
    label?: string
    note?: string
    error?: string
  }
  bleed_clerk?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    bleed_pass?: boolean
    bleed_ratio?: number | null
    label?: string
    note?: string
    error?: string
  }
  skip_twin_clerk?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    promote_ready?: boolean
    auto_promote?: boolean
    label?: string
    note?: string
    error?: string
  }
  clv_closer?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    complete?: number
    pass?: boolean
    label?: string
    note?: string
    error?: string
  }
  timer_digest?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    alive?: boolean
    status?: string
    label?: string
    note?: string
    error?: string
  }
  clerk_pulse?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    age_sec?: number | null
    cadence_sec?: number | null
    stale?: boolean
    soft_warn?: boolean
    refreshed_n?: number
    label?: string
    note?: string
    error?: string
  }
  /** Living upgrade insight≥3:1 city light (paper observe). */
  swarm_lights?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    pass?: boolean
    ratio?: number | null
    insight_n?: number
    betting_n?: number
    min_ratio?: number
    color?: string
    label?: string
    note?: string
    error?: string
  }
  completions?: {
    paper_only?: boolean
    eligible_completions_today?: number
    eligible_pnl_today?: number | null
    n?: number
    note?: string
    error?: string
  }
  green_day?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    green_n?: number
    red_n?: number
    all_fee_clear_green?: boolean
    label?: string
    note?: string
    error?: string
  }
  bleed?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    ratio?: number | null
    pass?: boolean
    label?: string
    note?: string
    error?: string
  }
  clv?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    n?: number
    complete?: number
    rate?: number | null
    pass?: boolean
    label?: string
    note?: string
    error?: string
  }
  calib_nag?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    tickets_n?: number
    auto_write_phi?: boolean
    label?: string
    note?: string
    error?: string
  }
  timer_heartbeat?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    alive?: boolean
    age_sec?: number | null
    label?: string
    note?: string
    error?: string
  }
  teller_living?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    memory_line?: string
    label?: string
    swarm_pass?: boolean
    floors_ok?: boolean
    eligible_completions_today?: number
    ritual_ok?: boolean | null
    ritual_nag?: boolean
    quiet_nag?: boolean
    quiet_age?: string
    quiet_age_h?: number | null
    quiet_age_label?: string
    note?: string
    error?: string
  }
  living_memory_line?: string
  fee_floors_assert?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    all_ok?: boolean
    label?: string
    venues?: Record<string, { floor?: number; live?: number; ok?: boolean }>
    note?: string
    error?: string
  }
  betting_expand_gate?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    allow_betting_expand?: boolean
    blocked?: boolean
    swarm_pass?: boolean
    swarm_ratio?: number | null
    label?: string
    reason?: string
    soft_copy?: string
    note?: string
    error?: string
  }
  dual_control_chip?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    signed_n?: number
    items_n?: number
    checklist_complete?: boolean
    arm_ready_paper?: boolean
    live_orders_enabled?: boolean
    label?: string
    note?: string
    error?: string
  }
  ruin_drill_chip?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    active?: boolean
    practiced_this_month?: boolean
    level?: string
    label?: string
    note?: string
    error?: string
  }
  living_doctor?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    ok?: boolean
    failed_n?: number
    label?: string
    note?: string
    error?: string
  }
  doctor_age?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    at?: string | null
    age_sec?: number | null
    ok_last?: boolean | null
    stale?: boolean
    label?: string
    note?: string
  }
  ritual_observe?: {
    paper_only?: boolean
    fee_floors_locked?: boolean
    ritual_ok?: boolean
    exit_ok?: boolean
    floors_ok?: boolean
    expand_ok?: boolean
    doctor_fresh?: boolean
    auto_publish?: boolean
    label?: string
    note?: string
    error?: string
  }
  ritual_soft_copy?: string
  ritual_discord?: string
  doctor_soft_copy?: string
  doctor_fresh?: boolean | null
  master?: {
    paper_only?: boolean
    version?: number
    priority?: string[]
    sunday_packet?: Desk['sunday_packet']
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
    swarm_lights?: Desk['swarm_lights']
    completions?: Desk['completions']
    towers?: unknown[]
    ritual_observe?: Desk['ritual_observe']
    ritual_soft_copy?: string
    ritual_discord?: string
    doctor_soft_copy?: string
    doctor_fresh?: boolean | null
    note?: string
  }
  teller_memory?: {
    paper_only?: boolean
    n_facts?: number
    n_mistakes?: number
    n_wins?: number
    updated_at?: string | null
    recent?: { kind?: string; bot?: string | null; text?: string; at?: string }[]
    note?: string
    error?: string
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
  /** City snapshot schema version (paper-bots/snapshot_schema.py). Missing on old desk builds. */
  schema_version?: number
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
  /** Server time (epoch seconds) when this shared snapshot was read. */
  cached_at?: number
}

export type DataMode = 'live' | 'offline'

export type SnapshotState = {
  snap: Snapshot | null
  mode: DataMode
  error: string | null
  updatedAt: number | null
  loading: boolean
}
