/**
 * Shared third-person grounded locomotion — vault teller UX.
 * W/S walk along facing · A/D turn (A=left / cam swings right) · Space jump · Shift sprint.
 * Office / wing walkers should call stepGroundedWalk with their own bounds + obstacles.
 */

import { MathUtils, Vector3 } from 'three'
import { clampToBounds, resolveObstacles, type FloorObstacle, type WalkBounds } from './bankWalk'

export const GROUNDED = {
  capsuleR: 0.32,
  eyeH: 1.55,
  bodyH: 1.45,
  walkSpeed: 5.25,
  sprintMul: 1.55,
  accel: 38,
  friction: 22,
  airCtrl: 0.35,
  jumpV: 6.15,
  gravity: 26,
  landDamp: 18,
  coyote: 0.12,
  jumpBuffer: 0.14,
  lookSens: 0.0021,
  turnSpeed: 2.45,
  turnSprint: 3.05,
  camBack: 2.65,
  camUp: 1.88,
  camSide: 0.38,
  camLerp: 11,
  bobAmt: 0.06,
  camWallPad: 0.55,
} as const

export type GroundedTune = Partial<{
  walkSpeed: number
  sprintMul: number
  accel: number
  friction: number
  airCtrl: number
  jumpV: number
  gravity: number
  landDamp: number
  coyote: number
  jumpBuffer: number
  turnSpeed: number
  turnSprint: number
  bobAmt: number
}>

/** Vault guest hero — snappier than shared defaults (office keeps GROUNDED). */
export const HERO_TUNE: GroundedTune = {
  walkSpeed: 5.55,
  sprintMul: 1.72,
  accel: 48,
  friction: 26,
  airCtrl: 0.48,
  jumpV: 6.85,
  gravity: 28,
  turnSpeed: 2.85,
  turnSprint: 3.55,
  bobAmt: 0.085,
  coyote: 0.16,
  jumpBuffer: 0.18,
}

export type GroundedState = {
  pos: Vector3
  vel: Vector3
  yaw: number
  pitch: number
  grounded: boolean
  coyote: number
  jumpBuf: number
  bobPhase: number
  camPos: Vector3
}

export type CamClamp = {
  minX: number
  maxX: number
  minZ: number
  maxZ: number
}

export type GroundedStepInput = {
  dt: number
  keys: Record<string, boolean>
  obstacles: FloorObstacle[]
  /** Primary floor clamp (AABB or custom). */
  clampXZ: (x: number, z: number) => { x: number; z: number }
  /** Optional soft pad so the follow cam stays inside walls. */
  camClamp?: CamClamp | null
  radius?: number
  /** Per-caller overrides (hero vault uses HERO_TUNE). */
  tune?: GroundedTune
  /**
   * Variable jump: if true and rising while jump key is up, cut ascent early.
   * Pass whether Space is currently held.
   */
  jumpHeld?: boolean
}

export type GroundedStepResult = {
  turn: number
  bob: number
  bobAmp: number
  lean: number
  pitchLean: number
  groundSpeed: number
  step: number
  leftLift: number
  rightLift: number
  /** Upward velocity — figure thrusters / squash use this. */
  velY: number
}

export function createGroundedState(
  x = 0,
  z = 0,
  yaw = Math.PI,
  pitch = 0.1,
): GroundedState {
  const backX = Math.sin(yaw) * -GROUNDED.camBack
  const backZ = Math.cos(yaw) * -GROUNDED.camBack
  return {
    pos: new Vector3(x, 0, z),
    vel: new Vector3(),
    yaw,
    pitch,
    grounded: true,
    coyote: 0,
    jumpBuf: 0,
    bobPhase: 0,
    camPos: new Vector3(x + backX, GROUNDED.camUp, z + backZ),
  }
}

export function resetGroundedState(s: GroundedState, x: number, z: number, yaw: number, pitch = 0.1) {
  s.pos.set(x, 0, z)
  s.vel.set(0, 0, 0)
  s.yaw = yaw
  s.pitch = pitch
  s.grounded = true
  s.coyote = 0
  s.jumpBuf = 0
  s.bobPhase = 0
  const backX = Math.sin(yaw) * -GROUNDED.camBack
  const backZ = Math.cos(yaw) * -GROUNDED.camBack
  s.camPos.set(x + backX, GROUNDED.camUp, z + backZ)
}

/** Apply mouse look deltas (call from mousemove when locked/dragging). */
export function applyLookDelta(s: GroundedState, movementX: number, movementY: number) {
  s.yaw -= movementX * GROUNDED.lookSens
  s.pitch = MathUtils.clamp(s.pitch - movementY * GROUNDED.lookSens, -0.35, 0.55)
}

/** Queue a jump from keydown (coyote + buffer consume happens in step). */
export function queueJump(s: GroundedState, buffer: number = GROUNDED.jumpBuffer) {
  s.jumpBuf = buffer
}

/**
 * One locomotion frame. Mutates `s`. Returns pose helpers for body / feet / camera.
 * A/D turn the body; W/S walk along facing — no strafe (vault teller UX).
 */
export function stepGroundedWalk(s: GroundedState, input: GroundedStepInput): GroundedStepResult {
  const dt = Math.min(0.033, input.dt)
  const k = input.keys
  const radius = input.radius ?? GROUNDED.capsuleR
  const t = input.tune ?? {}
  const walkSpeed = t.walkSpeed ?? GROUNDED.walkSpeed
  const sprintMul = t.sprintMul ?? GROUNDED.sprintMul
  const accel = t.accel ?? GROUNDED.accel
  const friction = t.friction ?? GROUNDED.friction
  const airCtrl = t.airCtrl ?? GROUNDED.airCtrl
  const jumpV = t.jumpV ?? GROUNDED.jumpV
  const gravity = t.gravity ?? GROUNDED.gravity
  const landDamp = t.landDamp ?? GROUNDED.landDamp
  const coyoteT = t.coyote ?? GROUNDED.coyote
  const turnSpeed = t.turnSpeed ?? GROUNDED.turnSpeed
  const turnSprint = t.turnSprint ?? GROUNDED.turnSprint
  const bobAmt = t.bobAmt ?? GROUNDED.bobAmt

  const turn = (k.a || k.arrowleft ? 1 : 0) - (k.d || k.arrowright ? 1 : 0)
  if (turn !== 0) {
    // Speed-scaled turn — slower at sprint so it doesn't whip.
    const spdScale = 1 - Math.min(0.28, Math.hypot(s.vel.x, s.vel.z) / (walkSpeed * sprintMul) * 0.28)
    const rate = (k.shift ? turnSprint : turnSpeed) * turn * spdScale
    s.yaw += rate * dt
  }

  const forward = (k.w || k.arrowup ? 1 : 0) - (k.s || k.arrowdown ? 1 : 0)
  const sin = Math.sin(s.yaw)
  const cos = Math.cos(s.yaw)
  const wishX = forward * sin
  const wishZ = forward * cos
  const maxSpeed = walkSpeed * (k.shift ? sprintMul : 1)
  const wishSpeed = forward ? maxSpeed : 0
  const control = s.grounded ? 1 : airCtrl

  if (wishSpeed > 0) {
    s.vel.x += wishX * accel * control * dt
    s.vel.z += wishZ * accel * control * dt
    const spd = Math.hypot(s.vel.x, s.vel.z)
    if (spd > maxSpeed) {
      s.vel.x = (s.vel.x / spd) * maxSpeed
      s.vel.z = (s.vel.z / spd) * maxSpeed
    }
  } else if (s.grounded) {
    const spd = Math.hypot(s.vel.x, s.vel.z)
    if (spd > 0.01) {
      // Turning while coasting bleeds a little extra speed (planted feel).
      const turnBleed = turn !== 0 ? 1.35 : 1
      const drop = Math.min(spd, friction * turnBleed * dt)
      s.vel.x *= (spd - drop) / spd
      s.vel.z *= (spd - drop) / spd
    } else {
      s.vel.x = 0
      s.vel.z = 0
    }
  }

  if (s.grounded) s.coyote = coyoteT
  else s.coyote = Math.max(0, s.coyote - dt)
  s.jumpBuf = Math.max(0, s.jumpBuf - dt)

  if (s.jumpBuf > 0 && s.coyote > 0) {
    s.vel.y = jumpV
    s.grounded = false
    s.coyote = 0
    s.jumpBuf = 0
  }
  // Variable jump height — release Space early to cut the hop.
  if (input.jumpHeld === false && !s.grounded && s.vel.y > 1.2) {
    s.vel.y *= 0.82
  }
  s.vel.y -= gravity * dt

  let nx = s.pos.x + s.vel.x * dt
  let nz = s.pos.z
  let hit = resolveObstacles(nx, nz, radius, input.obstacles)
  nx = hit.x
  nz = hit.z
  let clamped = input.clampXZ(nx, nz)
  if (clamped.x !== nx) s.vel.x *= 0.2
  nx = clamped.x

  nz = s.pos.z + s.vel.z * dt
  hit = resolveObstacles(nx, nz, radius, input.obstacles)
  nx = hit.x
  nz = hit.z
  clamped = input.clampXZ(nx, nz)
  if (clamped.z !== nz) s.vel.z *= 0.2
  nx = clamped.x
  nz = clamped.z

  s.pos.x = nx
  s.pos.z = nz
  s.pos.y += s.vel.y * dt
  if (s.pos.y <= 0) {
    if (s.vel.y < -0.5) s.vel.y = MathUtils.damp(s.vel.y, 0, landDamp, dt)
    else s.vel.y = 0
    s.pos.y = 0
    s.grounded = true
  }

  const groundSpeed = Math.hypot(s.vel.x, s.vel.z)
  if (s.grounded && groundSpeed > 0.35) {
    s.bobPhase += dt * (9.2 + groundSpeed * 1.35)
  } else {
    s.bobPhase = MathUtils.damp(s.bobPhase, 0, 10, dt)
  }
  const bobAmp = s.grounded ? Math.min(1, groundSpeed / 2.4) : 0
  const bob = Math.sin(s.bobPhase) * bobAmt * bobAmp
  const lean = turn !== 0 ? -turn * 0.12 : -s.vel.x * 0.012
  const pitchLean = s.grounded
    ? -groundSpeed * 0.012 * (forward >= 0 ? 1 : -0.6)
    : MathUtils.clamp(s.vel.y * -0.02, -0.12, 0.1)
  const step = Math.sin(s.bobPhase) * bobAmp
  const leftLift = Math.max(0, Math.sin(s.bobPhase)) * 0.06 * bobAmp
  const rightLift = Math.max(0, -Math.sin(s.bobPhase)) * 0.06 * bobAmp

  // Over-shoulder follow cam.
  const backX = Math.sin(s.yaw) * -GROUNDED.camBack + Math.cos(s.yaw) * GROUNDED.camSide
  const backZ = Math.cos(s.yaw) * -GROUNDED.camBack - Math.sin(s.yaw) * GROUNDED.camSide
  let wantCamX = s.pos.x + backX
  const wantCamY = s.pos.y + GROUNDED.camUp + bob + s.pitch * 0.55
  let wantCamZ = s.pos.z + backZ
  if (input.camClamp) {
    wantCamX = MathUtils.clamp(wantCamX, input.camClamp.minX, input.camClamp.maxX)
    wantCamZ = MathUtils.clamp(wantCamZ, input.camClamp.minZ, input.camClamp.maxZ)
  }
  s.camPos.x = MathUtils.damp(s.camPos.x, wantCamX, GROUNDED.camLerp, dt)
  s.camPos.y = MathUtils.damp(s.camPos.y, wantCamY, GROUNDED.camLerp, dt)
  s.camPos.z = MathUtils.damp(s.camPos.z, wantCamZ, GROUNDED.camLerp, dt)

  return {
    turn,
    bob,
    bobAmp,
    lean,
    pitchLean,
    groundSpeed,
    step,
    leftLift,
    rightLift,
    velY: s.vel.y,
  }
}

/** Default AABB clamp helper for rectangular halls. */
export function aabbClamp(bounds: WalkBounds) {
  return (x: number, z: number) => clampToBounds(x, z, bounds)
}

export function defaultWalkHint(locked: boolean, interactLabel?: string | null): string {
  if (interactLabel) return interactLabel
  return locked
    ? 'W/S walk · A/D turn · Space jump · Shift sprint · Esc unlock'
    : 'Click to look · W/S walk · A/D turn · Space jump · E talk'
}
