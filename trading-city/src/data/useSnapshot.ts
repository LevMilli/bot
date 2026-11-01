import { useEffect, useRef, useState } from 'react'
import type { Snapshot, SnapshotState } from '../types'

const POLL_MS = 8_000
const LIVE_URL =
  (import.meta.env.VITE_SNAPSHOT_URL as string | undefined) || '/api/pimp-trading.json'
const FIXTURE_URL = import.meta.env.BASE_URL + 'fixture-snapshot.json'

async function fetchJson(url: string, init?: RequestInit): Promise<Snapshot> {
  const res = await fetch(url, init)
  if (!res.ok) throw new Error(`${url} → ${res.status}`)
  return (await res.json()) as Snapshot
}

export function useSnapshot(pollMs = POLL_MS): SnapshotState {
  const [state, setState] = useState<SnapshotState>({
    snap: null,
    mode: 'live',
    error: null,
    updatedAt: null,
    loading: true,
  })
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    let timer: number | undefined

    const load = async () => {
      try {
        const snap = await fetchJson(LIVE_URL, { credentials: 'same-origin', cache: 'no-store' })
        if (!alive.current) return
        if (!snap.bots || !Array.isArray(snap.bots)) throw new Error('snapshot missing bots[]')
        setState({
          snap,
          mode: 'live',
          error: null,
          updatedAt: Date.now(),
          loading: false,
        })
      } catch (err) {
        try {
          const snap = await fetchJson(FIXTURE_URL)
          if (!alive.current) return
          setState({
            snap,
            mode: 'offline',
            error: err instanceof Error ? err.message : 'live unreachable',
            updatedAt: Date.now(),
            loading: false,
          })
        } catch (fallbackErr) {
          if (!alive.current) return
          setState((prev) => ({
            ...prev,
            loading: false,
            error:
              fallbackErr instanceof Error
                ? fallbackErr.message
                : 'could not load live or fixture snapshot',
          }))
        }
      }
    }

    void load()
    timer = window.setInterval(() => void load(), pollMs)
    return () => {
      alive.current = false
      if (timer) window.clearInterval(timer)
    }
  }, [pollMs])

  return state
}
