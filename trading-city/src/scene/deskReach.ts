/**
 * Shared desk targets so the keyboard, the mouse, and the bot's hands
 * stay on the same spots. Heights are the top of each device in world Y.
 */
export const KEY_TOP = 0.836
export const MOUSE_TOP = 0.846
/** Grip center sits this far above the surface it is touching. */
export const PALM = 0.042

export const KEYBOARD = { x: -0.3, z: 0.34 }
export const MOUSE = { x: 0.48, z: 0.4 }

export function typingHand(t: number, pace = 1) {
  const strike = Math.pow(Math.max(0, Math.sin(t * 9.5 * pace)), 5)
  const lift = (1 - strike) * 0.04
  return {
    x: KEYBOARD.x + Math.sin(t * 3.1 * pace) * 0.016,
    y: KEY_TOP + PALM + lift,
    z: KEYBOARD.z + Math.cos(t * 2.2 * pace) * 0.01,
  }
}

export function mouseHand(t: number) {
  return {
    x: MOUSE.x + Math.sin(t * 1.15) * 0.028,
    y: MOUSE_TOP + PALM,
    z: MOUSE.z + Math.cos(t * 0.85) * 0.02,
    yaw: Math.sin(t * 1.15) * 0.14,
  }
}
