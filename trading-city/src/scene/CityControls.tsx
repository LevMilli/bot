import { useEffect, useMemo, useRef } from 'react'
import { PerspectiveCamera } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import type { PerspectiveCamera as Cam } from 'three'
import * as THREE from 'three'

const LOOK = new THREE.Vector3(0, 0.4, -0.5)
/** Close enough to read a tower face, far enough to see the wall charts and tower tops. */
const MIN_DIST = 3.5
const MAX_DIST = 64
const MIN_PHI = 0.28
const MAX_PHI = 1.35
/** How quickly zoom eases toward the pinch/wheel target. */
const ZOOM_SMOOTH = 10
const ORBIT_DAMP = 4.5

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n))
}

type Ptr = { x: number; y: number }

/**
 * City camera:
 * - One finger / mouse click-hold drag → orbit the plaza (move the 3D world around)
 * - Two-finger pinch → smooth zoom in/out
 * - Mouse wheel → smooth zoom
 */
export function CityOrbitCamera() {
  const cam = useRef<Cam>(null)
  const { gl } = useThree()
  const reduced = useMemo(() => prefersReducedMotion(), [])

  const state = useRef({
    theta: Math.PI / 4,
    phi: 1.2,
    dist: 20,
    targetDist: 20,
    /** Active pointers (mouse + touch share Pointer Events). */
    pointers: new Map<number, Ptr>(),
    /** One-finger / mouse orbit */
    orbiting: false,
    lastX: 0,
    lastY: 0,
    velTheta: 0,
    velPhi: 0,
    /** Two-finger pinch */
    pinching: false,
    pinchStartSpan: 0,
    pinchStartDist: 20,
    /** Ignore tiny moves so a tap still selects towers. */
    moved: false,
  })

  useEffect(() => {
    const el = gl.domElement
    el.style.touchAction = 'none'
    el.style.userSelect = 'none'
    ;(el.style as CSSStyleDeclaration & { webkitUserSelect?: string }).webkitUserSelect = 'none'

    const s = () => state.current

    const spanOf = (pts: Ptr[]) => {
      if (pts.length < 2) return 0
      const dx = pts[0].x - pts[1].x
      const dy = pts[0].y - pts[1].y
      return Math.hypot(dx, dy)
    }

    const beginOrbit = (p: Ptr) => {
      const st = s()
      st.orbiting = true
      st.pinching = false
      st.lastX = p.x
      st.lastY = p.y
      st.velTheta = 0
      st.velPhi = 0
      st.moved = false
    }

    const beginPinch = () => {
      const st = s()
      const pts = [...st.pointers.values()]
      if (pts.length < 2) return
      st.orbiting = false
      st.pinching = true
      st.pinchStartSpan = Math.max(1, spanOf(pts))
      st.pinchStartDist = st.targetDist
      st.velTheta = 0
      st.velPhi = 0
    }

    const onDown = (e: PointerEvent) => {
      // Primary button / touch / pen only
      if (e.pointerType === 'mouse' && e.button !== 0) return
      const st = s()
      st.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
      try {
        el.setPointerCapture(e.pointerId)
      } catch {
        /* ignore */
      }

      if (st.pointers.size === 1) {
        beginOrbit({ x: e.clientX, y: e.clientY })
      } else if (st.pointers.size >= 2) {
        beginPinch()
      }
    }

    const onMove = (e: PointerEvent) => {
      const st = s()
      if (!st.pointers.has(e.pointerId)) return
      st.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })

      if (st.pointers.size >= 2 && st.pinching) {
        const pts = [...st.pointers.values()]
        const span = Math.max(1, spanOf(pts))
        // Larger span → zoom in (closer). Smooth via targetDist + frame lerp.
        const ratio = st.pinchStartSpan / span
        st.targetDist = clamp(st.pinchStartDist * ratio, MIN_DIST, MAX_DIST)
        st.moved = true
        return
      }

      if (!st.orbiting || st.pointers.size !== 1) return
      const dx = e.clientX - st.lastX
      const dy = e.clientY - st.lastY
      if (Math.abs(dx) + Math.abs(dy) > 2) st.moved = true
      st.lastX = e.clientX
      st.lastY = e.clientY
      const dTheta = -dx * 0.0055
      const dPhi = -dy * 0.0045
      st.theta += dTheta
      st.phi = clamp(st.phi + dPhi, MIN_PHI, MAX_PHI)
      st.velTheta = dTheta
      st.velPhi = dPhi
    }

    const onUp = (e: PointerEvent) => {
      const st = s()
      st.pointers.delete(e.pointerId)
      try {
        el.releasePointerCapture(e.pointerId)
      } catch {
        /* already released */
      }

      if (st.pointers.size === 0) {
        st.orbiting = false
        st.pinching = false
      } else if (st.pointers.size === 1) {
        // Dropped out of pinch → resume orbit with the remaining finger
        const rem = [...st.pointers.values()][0]
        beginOrbit(rem)
      } else {
        beginPinch()
      }
    }

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const st = s()
      st.targetDist = clamp(st.targetDist + e.deltaY * 0.05, MIN_DIST, MAX_DIST)
    }

    // Block browser page-zoom / scroll gestures on the canvas.
    const onGesture = (e: Event) => e.preventDefault()

    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointercancel', onUp)
    el.addEventListener('lostpointercapture', onUp)
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('gesturestart', onGesture as EventListener)
    el.addEventListener('gesturechange', onGesture as EventListener)
    return () => {
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointercancel', onUp)
      el.removeEventListener('lostpointercapture', onUp)
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('gesturestart', onGesture as EventListener)
      el.removeEventListener('gesturechange', onGesture as EventListener)
    }
  }, [gl])

  useFrame((_, dt) => {
    if (!cam.current) return
    const st = state.current
    const t = Math.min(1, dt * ZOOM_SMOOTH)
    st.dist += (st.targetDist - st.dist) * (reduced ? 1 : t)

    if (!st.orbiting && !st.pinching && !reduced) {
      st.theta += st.velTheta
      st.phi = clamp(st.phi + st.velPhi, MIN_PHI, MAX_PHI)
      const damp = Math.exp(-dt * ORBIT_DAMP)
      st.velTheta *= damp
      st.velPhi *= damp
    } else if (reduced) {
      st.velTheta = 0
      st.velPhi = 0
    }

    const x = LOOK.x + st.dist * Math.sin(st.phi) * Math.sin(st.theta)
    const y = LOOK.y + st.dist * Math.cos(st.phi)
    const z = LOOK.z + st.dist * Math.sin(st.phi) * Math.cos(st.theta)
    cam.current.position.set(x, y, z)
    cam.current.lookAt(LOOK)
  })

  return (
    <PerspectiveCamera ref={cam} makeDefault fov={42} near={0.08} far={360} position={[0, 17, 15]} />
  )
}
