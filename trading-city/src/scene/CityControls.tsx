import { useEffect, useMemo, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import * as THREE from 'three'

const LOOK = new THREE.Vector3(0, 0.4, -0.5)
const MIN_DIST = 10
const MAX_DIST = 28
const MIN_PHI = 0.35
const MAX_PHI = 1.25

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Click-and-hold drag orbit around the plaza. Wheel zooms. Release stops.
 * Starts at the high ¾ god-view used by the city refs.
 */
export function CityOrbitCamera() {
  const cam = useRef<Cam>(null)
  const { gl } = useThree()
  const reduced = useMemo(() => prefersReducedMotion(), [])

  const state = useRef({
    theta: Math.PI / 4,
    phi: 0.82,
    dist: 21.5,
    dragging: false,
    lastX: 0,
    lastY: 0,
    velTheta: 0,
    velPhi: 0,
  })

  useEffect(() => {
    const el = gl.domElement
    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return
      state.current.dragging = true
      state.current.lastX = e.clientX
      state.current.lastY = e.clientY
      state.current.velTheta = 0
      state.current.velPhi = 0
      el.setPointerCapture(e.pointerId)
    }
    const onMove = (e: PointerEvent) => {
      if (!state.current.dragging) return
      const dx = e.clientX - state.current.lastX
      const dy = e.clientY - state.current.lastY
      state.current.lastX = e.clientX
      state.current.lastY = e.clientY
      const dTheta = -dx * 0.005
      const dPhi = -dy * 0.004
      state.current.theta += dTheta
      state.current.phi = Math.min(MAX_PHI, Math.max(MIN_PHI, state.current.phi + dPhi))
      state.current.velTheta = dTheta
      state.current.velPhi = dPhi
    }
    const onUp = (e: PointerEvent) => {
      state.current.dragging = false
      try {
        el.releasePointerCapture(e.pointerId)
      } catch {
        /* already released */
      }
    }
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      state.current.dist = Math.min(
        MAX_DIST,
        Math.max(MIN_DIST, state.current.dist + e.deltaY * 0.02),
      )
    }

    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointercancel', onUp)
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointercancel', onUp)
      el.removeEventListener('wheel', onWheel)
    }
  }, [gl])

  useFrame((_, dt) => {
    if (!cam.current) return
    const s = state.current
    if (!s.dragging && !reduced) {
      s.theta += s.velTheta
      s.phi = Math.min(MAX_PHI, Math.max(MIN_PHI, s.phi + s.velPhi))
      const damp = Math.exp(-dt * 4.5)
      s.velTheta *= damp
      s.velPhi *= damp
    } else if (reduced) {
      s.velTheta = 0
      s.velPhi = 0
    }

    const x = LOOK.x + s.dist * Math.sin(s.phi) * Math.sin(s.theta)
    const y = LOOK.y + s.dist * Math.cos(s.phi)
    const z = LOOK.z + s.dist * Math.sin(s.phi) * Math.cos(s.theta)
    cam.current.position.set(x, y, z)
    cam.current.lookAt(LOOK)
  })

  return (
    <PerspectiveCamera ref={cam} makeDefault fov={42} near={0.1} far={200} position={[0, 17, 15]} />
  )
}
