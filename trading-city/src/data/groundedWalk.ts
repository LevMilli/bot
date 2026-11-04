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
export function queueJump(s: GroundedState) {
  s.jumpBuf = GROUNDED.jumpBuffer
}

/**
 * One locomotion frame. Mutates `s`. Returns pose helpers for body / feet / camera.
 * A/D turn the body; W/S walk along facing — no strafe (vault teller UX).
 */
export function stepGroundedWalk(s: GroundedState, input: GroundedStepInput): GroundedStepResult {
  const dt = Math.min(0.033, input.dt)
  const k = input.keys
  const radius = input.radius ?? GROUNDED.capsuleR
  const G = GROUNDED

  const turn = (k.a || k.arrowleft ? 1 : 0) - (k.d || k.arrowright ? 1 : 0)
  if (turn !== 0) {
    const rate = (k.shift ? G.turnSprint : G.turnSpeed) * turn
    s.yaw += rate * dt
  }

  const forward = (k.w || k.arrowup ? 1 : 0) - (k.s || k.arrowdown ? 1 : 0)
  const sin = Math.sin(s.yaw)
  const cos = Math.cos(s.yaw)
  const wishX = forward * sin
  const wishZ = forward * cos
  const maxSpeed = G.walkSpeed * (k.shift ? G.sprintMul : 1)
  const wishSpeed = forward ? maxSpeed : 0
  const control = s.grounded ? 1 : G.airCtrl

  if (wishSpeed > 0) {
    s.vel.x += wishX * G.accel * control * dt
    s.vel.z += wishZ * G.accel * control * dt
    const spd = Math.hypot(s.vel.x, s.vel.z)
    if (spd > maxSpeed) {
      s.vel.x = (s.vel.x / spd) * maxSpeed
      s.vel.z = (s.vel.z / spd) * maxSpeed
    }
  } else if (s.grounded) {
    const spd = Math.hypot(s.vel.x, s.vel.z)
    if (spd > 0.01) {
      const drop = Math.min(spd, G.friction * dt)
      s.vel.x *= (spd - drop) / spd
      s.vel.z *= (spd - drop) / spd
    } else {
      s.vel.x = 0
      s.vel.z = 0
    }
  }

  if (s.grounded) s.coyote = G.coyote
  else s.coyote = Math.max(0, s.coyote - dt)
  s.jumpBuf = Math.max(0, s.jumpBuf - dt)

  if (s.jumpBuf > 0 && s.coyote > 0) {
    s.vel.y = G.jumpV
    s.grounded = false
    s.coyote = 0
    s.jumpBuf = 0
  }
  s.vel.y -= G.gravity * dt

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
    if (s.vel.y < -0.5) s.vel.y = MathUtils.damp(s.vel.y, 0, G.landDamp, dt)
    else s.vel.y = 0
    s.pos.y = 0
    s.grounded = true
  }

  const groundSpeed = Math.hypot(s.vel.x, s.vel.z)
  if (s.grounded && groundSpeed > 0.35) {
    s.bobPhase += dt * (8.6 + groundSpeed * 1.15)
  } else {
    s.bobPhase = MathUtils.damp(s.bobPhase, 0, 10, dt)
  }
  const bobAmp = s.grounded ? Math.min(1, groundSpeed / 2.6) : 0
  const bob = Math.sin(s.bobPhase) * G.bobAmt * bobAmp
  const lean = turn !== 0 ? -turn * 0.09 : -s.vel.x * 0.01
  const pitchLean = s.grounded ? -s.vel.z * 0.008 * Math.cos(s.yaw) : 0
  const step = Math.sin(s.bobPhase) * bobAmp
  const leftLift = Math.max(0, Math.sin(s.bobPhase)) * 0.05 * bobAmp
  const rightLift = Math.max(0, -Math.sin(s.bobPhase)) * 0.05 * bobAmp

  // Over-shoulder follow cam.
  const backX = Math.sin(s.yaw) * -G.camBack + Math.cos(s.yaw) * G.camSide
  const backZ = Math.cos(s.yaw) * -G.camBack - Math.sin(s.yaw) * G.camSide
  let wantCamX = s.pos.x + backX
  const wantCamY = s.pos.y + G.camUp + bob + s.pitch * 0.55
  let wantCamZ = s.pos.z + backZ
  if (input.camClamp) {
    wantCamX = MathUtils.clamp(wantCamX, input.camClamp.minX, input.camClamp.maxX)
    wantCamZ = MathUtils.clamp(wantCamZ, input.camClamp.minZ, input.camClamp.maxZ)
  }
  s.camPos.x = MathUtils.damp(s.camPos.x, wantCamX, G.camLerp, dt)
  s.camPos.y = MathUtils.damp(s.camPos.y, wantCamY, G.camLerp, dt)
  s.camPos.z = MathUtils.damp(s.camPos.z, wantCamZ, G.camLerp, dt)

  return { turn, bob, bobAmp, lean, pitchLean, groundSpeed, step, leftLift, rightLift }
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
