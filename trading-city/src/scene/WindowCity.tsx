import { useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import type { BotRow } from '../types'
import { CityContents } from './CityScene'

/**
 * Wider, higher overlook than the city page so the vault and beams sit in the
 * upper glass — the desk monitors cover the bottom of the pane.
 */
function OverlookCamera() {
  const cam = useRef<Cam>(null)
  useFrame(() => {
    cam.current?.lookAt(0, 1.5, 5.1)
  })
  return (
    <PerspectiveCamera
      ref={cam}
      makeDefault
      fov={46}
      aspect={1536 / 512}
      near={0.1}
      far={220}
      position={[2.2, 11.2, 14.4]}
    />
  )
}

/**
 * Live PIMP-CITY plaza drawn into the office glass.
 * A second camera keeps the vault, beams, and ring in the same composition as the city view.
 */
export function CityGlass({ bots }: { bots: BotRow[] }) {
  return (
    <>
      <color attach="background" args={['#0c0424']} />
      <fog attach="fog" args={['#1a0740', 28, 72]} />
      <OverlookCamera />
      <CityContents bots={bots} selectedId={null} onSelect={() => {}} />
    </>
  )
}
