import { useMemo, useRef, type MutableRefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import { CanvasTexture, MathUtils, type Group, type MeshStandardMaterial } from 'three'

/**
 * Master player avatar — industrial bank-bot DNA with a guest-VIP upgrade.
 * Same gunmetal + neon language as IndustrialBotFigure, but denser plating,
 * guest heraldry, backpack pack, and locomotion-driven limbs for third-person.
 */

const ARMOR = '#121218'
const ARMOR_DARK = '#08080c'
const ARMOR_EDGE = '#1c1c24'
const METAL = '#2a2a32'
/** Guest accent — cyan trust chrome so the player reads above purple tellers. */
const ACCENT = '#2de2e6'
const ACCENT_DIM = '#1a8890'
const GOLD = '#f9c80e'
const GRAFFITI = '#f2f2f0'

export type PlayerHeroMotion = {
  /** −1..1 gait sine from groundedWalk */
  step: number
  bobAmp: number
  groundSpeed: number
  grounded: boolean
  jumping: boolean
  sprinting: boolean
  turn: number
}

function armor(roughness = 0.55, metalness = 0.68) {
  return {
    color: ARMOR,
    roughness,
    metalness,
    emissive: '#041018',
    emissiveIntensity: 0.1,
  }
}

function neon(color: string = ACCENT, intensity = 2.1) {
  return {
    color,
    emissive: color,
    emissiveIntensity: intensity,
    roughness: 0.18,
    metalness: 0.22,
    toneMapped: false as const,
  }
}

function LedStrip({
  position,
  rotation,
  size = [0.12, 0.018, 0.012],
  color = ACCENT,
}: {
  position: [number, number, number]
  rotation?: [number, number, number]
  size?: [number, number, number]
  color?: string
}) {
  return (
    <mesh position={position} rotation={rotation}>
      <boxGeometry args={size} />
      <meshStandardMaterial {...neon(color, 1.65)} />
    </mesh>
  )
}

function LedDot({
  position,
  r = 0.012,
  color = ACCENT,
}: {
  position: [number, number, number]
  r?: number
  color?: string
}) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[r, 10, 10]} />
      <meshStandardMaterial {...neon(color, 1.9)} />
    </mesh>
  )
}

function Bolt({ position }: { position: [number, number, number] }) {
  return (
    <mesh position={position}>
      <cylinderGeometry args={[0.009, 0.009, 0.012, 8]} />
      <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.28} />
    </mesh>
  )
}

function CrownMark({ scale = 1 }: { scale?: number }) {
  return (
    <group scale={scale}>
      <mesh position={[0, 0.01, 0]}>
        <boxGeometry args={[0.08, 0.022, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.04, 0]}>
        <boxGeometry args={[0.02, 0.045, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[-0.03, 0.032, 0]} rotation={[0, 0, 0.35]}>
        <boxGeometry args={[0.018, 0.04, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[0.03, 0.032, 0]} rotation={[0, 0, -0.35]}>
        <boxGeometry args={[0.018, 0.04, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
    </group>
  )
}

const TEX_CACHE = new Map<string, CanvasTexture>()

function guestTexture(kind: 'pauldron' | 'unit' | 'pack') {
  const key = `guest:${kind}`
  const hit = TEX_CACHE.get(key)
  if (hit) return hit
  const c = document.createElement('canvas')
  c.width = kind === 'pauldron' ? 256 : 128
  c.height = kind === 'pauldron' ? 256 : 128
  const ctx = c.getContext('2d')!
  ctx.clearRect(0, 0, c.width, c.height)
  ctx.fillStyle = GRAFFITI
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  if (kind === 'pauldron') {
    ctx.font = 'bold 34px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('APEX', 128, 70)
    ctx.font = 'bold 30px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('TRUST', 128, 110)
    ctx.fillStyle = GOLD
    ctx.font = 'bold 28px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('GUEST', 128, 160)
    ctx.fillStyle = ACCENT
    ctx.fillRect(70, 190, 116, 8)
    ctx.fillStyle = GRAFFITI
    ctx.fillRect(88, 210, 4, 18)
    ctx.fillRect(118, 208, 3, 22)
    ctx.fillRect(148, 212, 4, 14)
  } else if (kind === 'pack') {
    ctx.fillStyle = ACCENT
    ctx.font = 'bold 42px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('VAULT', 64, 48)
    ctx.fillStyle = GOLD
    ctx.font = 'bold 36px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('01', 64, 92)
  } else {
    ctx.fillStyle = GOLD
    ctx.font = 'bold 64px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('01', 64, 68)
  }
  const tex = new CanvasTexture(c)
  tex.needsUpdate = true
  TEX_CACHE.set(key, tex)
  return tex
}

function HeroArm({
  side,
  motion,
}: {
  side: -1 | 1
  motion: MutableRefObject<PlayerHeroMotion>
}) {
  const ref = useRef<Group>(null)
  const fore = useRef<Group>(null)

  useFrame((_, dt) => {
    if (!ref.current || !fore.current) return
    const m = motion.current
    const swing = m.step * (side < 0 ? 1 : -1) * (0.55 + m.bobAmp * 0.5)
    const hang = m.jumping ? -0.35 : -0.15
    const wantX = hang + swing * 0.9
    const wantZ = -side * (0.22 + (m.sprinting ? 0.08 : 0)) + m.turn * side * -0.06
    ref.current.rotation.x = MathUtils.damp(ref.current.rotation.x, wantX, 14, dt)
    ref.current.rotation.z = MathUtils.damp(ref.current.rotation.z, wantZ, 12, dt)
    fore.current.rotation.x = MathUtils.damp(
      fore.current.rotation.x,
      -0.35 + Math.abs(swing) * 0.55 + (m.jumping ? 0.2 : 0),
      14,
      dt,
    )
  })

  return (
    <group ref={ref} position={[side * 0.36, 0.82, 0]} rotation={[-0.15, 0, -side * 0.22]}>
      <mesh>
        <sphereGeometry args={[0.078, 16, 14]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.78} roughness={0.38} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.088, 0.014, 8, 26]} />
        <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.25} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.1, 0.006, 6, 24]} />
        <meshStandardMaterial {...neon(GOLD, 1.1)} />
      </mesh>
      <LedDot position={[0, 0.02, 0.085]} r={0.012} color={GOLD} />

      <mesh position={[0, 0.18, 0]}>
        <boxGeometry args={[0.12, 0.36, 0.12]} />
        <meshStandardMaterial {...armor(0.5, 0.72)} />
      </mesh>
      <mesh position={[0, 0.18, 0]}>
        <boxGeometry args={[0.095, 0.34, 0.095]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.65} />
      </mesh>
      <LedStrip position={[side * 0.062, 0.18, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.24, 0.016, 0.01]} />
      <LedStrip
        position={[side * 0.062, 0.18, 0]}
        rotation={[0, 0, Math.PI / 2]}
        size={[0.18, 0.01, 0.008]}
        color={GOLD}
      />
      <Bolt position={[side * 0.05, 0.08, 0.05]} />
      <Bolt position={[side * 0.05, 0.26, 0.05]} />

      <mesh position={[0, 0.38, 0]}>
        <sphereGeometry args={[0.06, 14, 12]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.82} roughness={0.32} />
      </mesh>
      <mesh position={[0, 0.38, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.068, 0.011, 8, 22]} />
        <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.24} />
      </mesh>

      <group ref={fore} position={[0, 0.38, 0]} rotation={[-0.4, 0, 0]}>
        <mesh position={[0, 0.16, 0]}>
          <boxGeometry args={[0.1, 0.32, 0.1]} />
          <meshStandardMaterial {...armor(0.48, 0.74)} />
        </mesh>
        <mesh position={[-side * 0.045, 0.16, 0]}>
          <boxGeometry args={[0.022, 0.24, 0.055]} />
          <meshStandardMaterial
            color="#050508"
            metalness={0.4}
            roughness={0.65}
            emissive={ACCENT_DIM}
            emissiveIntensity={0.45}
          />
        </mesh>
        <LedStrip position={[side * 0.055, 0.16, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.24, 0.014, 0.01]} />
        {/* Guest cuff band */}
        <mesh position={[0, 0.3, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.055, 0.01, 8, 20]} />
          <meshStandardMaterial {...neon(GOLD, 1.35)} />
        </mesh>
        {/* Mechanical hand */}
        <group position={[0, 0.36, 0]}>
          <mesh>
            <boxGeometry args={[0.08, 0.055, 0.06]} />
            <meshStandardMaterial {...armor(0.45, 0.75)} />
          </mesh>
          <LedStrip position={[0, 0, 0.034]} size={[0.055, 0.012, 0.008]} color={GOLD} />
          {([-1, 0, 1] as const).map((f) => (
            <mesh key={f} position={[f * 0.024, 0.06, 0.012]} rotation={[0.2, 0, f * 0.1]}>
              <boxGeometry args={[0.02, 0.1, 0.024]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.4} />
            </mesh>
          ))}
        </group>
      </group>
    </group>
  )
}

function HeroLeg({
  side,
  motion,
}: {
  side: -1 | 1
  motion: MutableRefObject<PlayerHeroMotion>
}) {
  const thigh = useRef<Group>(null)
  const shin = useRef<Group>(null)

  useFrame((_, dt) => {
    if (!thigh.current || !shin.current) return
    const m = motion.current
    const swing = m.step * (side < 0 ? 1 : -1)
    const wantThigh = m.jumping ? -0.55 : swing * 0.7 * (0.4 + m.bobAmp)
    const wantShin = m.jumping ? 0.85 : Math.max(0, -swing) * 0.9 * m.bobAmp + 0.12
    thigh.current.rotation.x = MathUtils.damp(thigh.current.rotation.x, wantThigh, 16, dt)
    shin.current.rotation.x = MathUtils.damp(shin.current.rotation.x, wantShin, 16, dt)
  })

  return (
    <group position={[side * 0.13, 0.08, 0]}>
      <group ref={thigh}>
        <mesh position={[0, -0.16, 0.02]} rotation={[0.08, 0, side * 0.04]}>
          <boxGeometry args={[0.115, 0.34, 0.12]} />
          <meshStandardMaterial {...armor(0.55, 0.6)} />
        </mesh>
        <mesh position={[0, -0.16, 0.02]}>
          <boxGeometry args={[0.09, 0.3, 0.09]} />
          <meshStandardMaterial color={ARMOR_DARK} metalness={0.45} roughness={0.7} />
        </mesh>
        <LedStrip position={[side * 0.06, -0.14, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.18, 0.012, 0.009]} />
        <Bolt position={[side * 0.05, -0.05, 0.05]} />
        <Bolt position={[side * 0.05, -0.22, 0.05]} />

        <group ref={shin} position={[0, -0.34, 0.04]}>
          <mesh position={[0, -0.16, 0.02]} rotation={[0.18, 0, 0]}>
            <boxGeometry args={[0.1, 0.3, 0.11]} />
            <meshStandardMaterial {...armor(0.58, 0.58)} />
          </mesh>
          <LedStrip position={[side * 0.055, -0.14, 0.02]} rotation={[0, 0, Math.PI / 2]} size={[0.16, 0.01, 0.008]} color={GOLD} />
          {/* Boot */}
          <mesh position={[0, -0.34, 0.08]} rotation={[0.28, 0, 0]}>
            <boxGeometry args={[0.12, 0.08, 0.22]} />
            <meshStandardMaterial color={ARMOR_DARK} roughness={0.5} metalness={0.5} />
          </mesh>
          <mesh position={[0, -0.3, 0.16]} rotation={[0.28, 0, 0]}>
            <boxGeometry args={[0.11, 0.05, 0.08]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.35} />
          </mesh>
          <LedStrip position={[0, -0.32, 0.18]} size={[0.08, 0.012, 0.01]} />
        </group>
      </group>
    </group>
  )
}

/**
 * Hero guest bot for vault third-person control.
 * Drive limbs with `motion` ref updated each frame from groundedWalk.
 */
export function PlayerHeroFigure({
  motion,
}: {
  motion: MutableRefObject<PlayerHeroMotion>
}) {
  const root = useRef<Group>(null)
  const torso = useRef<Group>(null)
  const head = useRef<Group>(null)
  const packGlow = useRef<MeshStandardMaterial>(null)
  const chestPulse = useRef<MeshStandardMaterial>(null)
  const maps = useMemo(
    () => ({
      pauldron: guestTexture('pauldron'),
      unit: guestTexture('unit'),
      pack: guestTexture('pack'),
    }),
    [],
  )

  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime()
    const m = motion.current
    if (root.current) {
      const squash = m.jumping ? 0.94 : 1 + Math.sin(t * 1.4) * 0.008 * (1 - m.bobAmp * 0.5)
      const stretch = m.jumping ? 1.05 : 1
      root.current.scale.set(1 / Math.sqrt(squash), squash * stretch, 1 / Math.sqrt(squash))
    }
    if (torso.current) {
      const pitch = m.sprinting ? 0.08 : m.jumping ? -0.06 : m.groundSpeed * 0.012
      torso.current.rotation.x = MathUtils.damp(torso.current.rotation.x, pitch, 10, dt)
      torso.current.rotation.z = MathUtils.damp(torso.current.rotation.z, -m.turn * 0.05, 10, dt)
    }
    if (head.current) {
      head.current.rotation.y = Math.sin(t * 0.55) * 0.06 * (1 - m.bobAmp * 0.4)
      head.current.rotation.x = MathUtils.damp(
        head.current.rotation.x,
        m.sprinting ? 0.08 : Math.sin(t * 0.7) * 0.04,
        8,
        dt,
      )
    }
    if (chestPulse.current) {
      chestPulse.current.emissiveIntensity = 1.4 + Math.sin(t * 2.8) * 0.35 + (m.sprinting ? 0.4 : 0)
    }
    if (packGlow.current) {
      packGlow.current.emissiveIntensity =
        (m.sprinting ? 2.2 : m.jumping ? 1.8 : 1.1) + Math.sin(t * 4.2) * 0.25
    }
  })

  // Feet sit on y=0: boot sole ≈ −0.64 in local space → lift root.
  return (
    <group ref={root} position={[0, 0.64, 0]} scale={1} frustumCulled={false}>
      {/* Soft self-key so gunmetal reads against the dark hall */}
      <pointLight position={[0, 1.2, 0.55]} intensity={0.55} color="#9ef6ff" distance={3.8} />
      <pointLight position={[0, 0.9, -0.5]} intensity={0.35} color="#f9c80e" distance={2.8} />
      <group ref={torso}>
        {/* Hip / pelvis cage */}
        <mesh position={[0, 0.16, 0]}>
          <boxGeometry args={[0.32, 0.18, 0.24]} />
          <meshStandardMaterial {...armor(0.58, 0.62)} />
        </mesh>
        <LedStrip position={[0, 0.16, 0.13]} size={[0.18, 0.014, 0.01]} color={GOLD} />
        {/* Utility belt */}
        <mesh position={[0, 0.24, 0]}>
          <boxGeometry args={[0.36, 0.05, 0.28]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.35} />
        </mesh>
        {([-0.12, 0, 0.12] as const).map((x) => (
          <mesh key={x} position={[x, 0.24, 0.145]}>
            <boxGeometry args={[0.05, 0.04, 0.03]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.6} roughness={0.45} />
          </mesh>
        ))}

        {/* Heavy chest */}
        <mesh position={[0, 0.58, 0.02]}>
          <boxGeometry args={[0.48, 0.58, 0.34]} />
          <meshStandardMaterial {...armor(0.5, 0.7)} />
        </mesh>
        {([-1, 1] as const).map((side) => (
          <mesh key={side} position={[side * 0.26, 0.58, 0.02]}>
            <boxGeometry args={[0.07, 0.46, 0.28]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.38} />
          </mesh>
        ))}
        <mesh position={[0, 0.58, 0]}>
          <boxGeometry args={[0.36, 0.5, 0.24]} />
          <meshStandardMaterial
            color={ARMOR_DARK}
            metalness={0.45}
            roughness={0.68}
            emissive={ACCENT_DIM}
            emissiveIntensity={0.32}
          />
        </mesh>
        {/* Spine stack */}
        <mesh position={[0, 0.58, -0.14]}>
          <boxGeometry args={[0.07, 0.52, 0.06]} />
          <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.3} />
        </mesh>
        {[0.4, 0.5, 0.6, 0.7].map((y) => (
          <mesh key={y} position={[0, y, -0.16]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.05, 0.009, 6, 16]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.28} />
          </mesh>
        ))}
        <LedStrip position={[0, 0.58, -0.175]} rotation={[Math.PI / 2, 0, 0]} size={[0.045, 0.4, 0.012]} />

        {/* Chest hero plate */}
        <mesh position={[0, 0.62, 0.175]}>
          <boxGeometry args={[0.22, 0.16, 0.03]} />
          <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.35} />
        </mesh>
        <mesh position={[0, 0.62, 0.195]}>
          <boxGeometry args={[0.16, 0.1, 0.012]} />
          <meshStandardMaterial ref={chestPulse} {...neon(ACCENT, 1.5)} />
        </mesh>
        <LedStrip position={[-0.15, 0.72, 0.175]} size={[0.09, 0.014, 0.01]} color={GOLD} />
        <LedStrip position={[0.15, 0.72, 0.175]} size={[0.09, 0.014, 0.01]} color={GOLD} />
        <mesh position={[0, 0.48, 0.175]}>
          <boxGeometry args={[0.24, 0.016, 0.01]} />
          <meshStandardMaterial {...neon(GOLD, 1.3)} />
        </mesh>

        {/* Shoulder collar ring */}
        <mesh position={[0, 0.88, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.22, 0.02, 8, 30]} />
          <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.25} />
        </mesh>
        <mesh position={[0, 0.88, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.245, 0.008, 6, 28]} />
          <meshStandardMaterial {...neon(GOLD, 1.0)} />
        </mesh>

        {/* Pauldrons — guest heraldry */}
        {([-1, 1] as const).map((side) => (
          <group key={side} position={[side * 0.34, 0.94, 0.04]}>
            <mesh rotation={[0.14, side * 0.22, side * 0.45]}>
              <boxGeometry args={[0.3, 0.18, 0.34]} />
              <meshStandardMaterial {...armor(0.45, 0.76)} />
            </mesh>
            <mesh position={[0, 0.07, 0]} rotation={[0.14, side * 0.22, side * 0.45]}>
              <boxGeometry args={[0.32, 0.035, 0.36]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.32} />
            </mesh>
            {/* Gold rim edge */}
            <mesh position={[0, 0.09, 0.02]} rotation={[0.14, side * 0.22, side * 0.45]}>
              <boxGeometry args={[0.28, 0.015, 0.02]} />
              <meshStandardMaterial {...neon(GOLD, 1.15)} />
            </mesh>
            <LedStrip position={[side * 0.02, 0.0, 0.14]} size={[0.16, 0.014, 0.01]} />
            <LedStrip position={[side * 0.02, -0.045, 0.14]} size={[0.12, 0.01, 0.008]} color={GOLD} />
            <Bolt position={[side * 0.09, 0.05, 0.12]} />
            <Bolt position={[side * 0.09, -0.04, 0.12]} />
            <Bolt position={[side * 0.09, 0.05, -0.08]} />
            <mesh position={[side * 0.15, 0.02, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <planeGeometry args={[0.22, 0.22]} />
              <meshBasicMaterial map={maps.pauldron} transparent toneMapped={false} depthWrite={false} />
            </mesh>
            <group position={[side * 0.155, 0.08, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <CrownMark scale={1.05} />
            </group>
          </group>
        ))}

        {/* Guest backpack / vault pack */}
        <group position={[0, 0.58, -0.28]}>
          <mesh>
            <boxGeometry args={[0.3, 0.42, 0.16]} />
            <meshStandardMaterial {...armor(0.5, 0.7)} />
          </mesh>
          <mesh position={[0, 0, -0.02]}>
            <boxGeometry args={[0.24, 0.34, 0.12]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.6} />
          </mesh>
          <mesh position={[0, -0.05, -0.1]}>
            <cylinderGeometry args={[0.06, 0.08, 0.08, 12]} />
            <meshStandardMaterial ref={packGlow} {...neon(ACCENT, 1.4)} />
          </mesh>
          <mesh position={[0, 0.12, -0.09]}>
            <planeGeometry args={[0.16, 0.16]} />
            <meshBasicMaterial map={maps.pack} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <LedStrip position={[0, 0.18, -0.09]} size={[0.14, 0.012, 0.01]} color={GOLD} />
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[side * 0.1, 0.05, -0.12]} rotation={[0.4, 0, side * 0.15]}>
              <boxGeometry args={[0.04, 0.16, 0.03]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.4} />
            </mesh>
          ))}
        </group>

        {/* Capelet panels */}
        {([-1, 1] as const).map((side) => (
          <mesh key={side} position={[side * 0.2, 0.42, -0.08]} rotation={[0.25, side * 0.15, side * 0.35]}>
            <boxGeometry args={[0.12, 0.36, 0.02]} />
            <meshStandardMaterial
              color={ARMOR_DARK}
              metalness={0.35}
              roughness={0.7}
              transparent
              opacity={0.92}
            />
          </mesh>
        ))}

        <LedDot position={[-0.12, 0.98, 0.1]} r={0.012} color={GOLD} />
        <LedDot position={[0.12, 0.98, 0.1]} r={0.012} color={GOLD} />

        {/* Helmet */}
        <group ref={head} position={[0, 1.08, 0.02]}>
          <mesh position={[0, -0.05, 0]}>
            <cylinderGeometry args={[0.05, 0.06, 0.11, 12]} />
            <meshStandardMaterial
              color={ARMOR_DARK}
              metalness={0.72}
              roughness={0.38}
              emissive={ACCENT_DIM}
              emissiveIntensity={0.5}
            />
          </mesh>
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[side * 0.038, -0.04, 0.02]}>
              <cylinderGeometry args={[0.011, 0.011, 0.1, 6]} />
              <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.22} />
            </mesh>
          ))}

          <mesh position={[0, 0.16, 0.02]}>
            <boxGeometry args={[0.4, 0.34, 0.42]} />
            <meshStandardMaterial {...armor(0.45, 0.76)} />
          </mesh>
          <mesh position={[0, 0.16, 0.02]}>
            <boxGeometry args={[0.012, 0.32, 0.43]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.55} />
          </mesh>
          <mesh position={[0, 0.34, 0.02]}>
            <boxGeometry args={[0.36, 0.08, 0.38]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.74} roughness={0.36} />
          </mesh>
          {/* Visor HUD bar */}
          <mesh position={[0, 0.15, 0.2]} rotation={[-0.35, 0, 0]}>
            <boxGeometry args={[0.34, 0.14, 0.06]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.3} />
          </mesh>
          <mesh position={[0, 0.15, 0.235]} rotation={[-0.35, 0, 0]}>
            <boxGeometry args={[0.28, 0.05, 0.02]} />
            <meshStandardMaterial {...neon(ACCENT, 1.8)} />
          </mesh>
          <LedDot position={[-0.07, 0.17, 0.24]} r={0.022} />
          <LedDot position={[0.07, 0.17, 0.24]} r={0.022} />
          <LedDot position={[0, 0.11, 0.245]} r={0.015} color={GOLD} />

          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.185, 0.15, 0.02]}>
              <mesh>
                <boxGeometry args={[0.024, 0.07, 0.16]} />
                <meshStandardMaterial color="#050508" metalness={0.5} roughness={0.5} />
              </mesh>
              {([-0.05, -0.017, 0.017, 0.05] as const).map((z) => (
                <LedDot key={z} position={[side * 0.014, 0, z]} r={0.012} color={z === 0.05 ? GOLD : ACCENT} />
              ))}
            </group>
          ))}

          <LedStrip position={[0, 0.02, 0.16]} size={[0.16, 0.022, 0.012]} color={GOLD} />
          <mesh position={[0, 0.02, 0.14]}>
            <boxGeometry args={[0.2, 0.045, 0.09]} />
            <meshStandardMaterial
              color={ARMOR_DARK}
              metalness={0.72}
              roughness={0.38}
              emissive={ACCENT_DIM}
              emissiveIntensity={0.35}
            />
          </mesh>

          {/* Twin blade antennae — longer + gold tips */}
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.1, 0.3, -0.14]} rotation={[0.45, 0, side * 0.25]}>
              <mesh position={[0, 0.24, 0]}>
                <boxGeometry args={[0.032, 0.5, 0.055]} />
                <meshStandardMaterial color={ARMOR_EDGE} metalness={0.8} roughness={0.3} />
              </mesh>
              {[0.08, 0.2, 0.32].map((y) => (
                <mesh key={y} position={[0, y, 0.01]}>
                  <boxGeometry args={[0.036, 0.055, 0.025]} />
                  <meshStandardMaterial color={ARMOR_DARK} />
                </mesh>
              ))}
              <mesh position={[0, 0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[0.034, 0.034, 0.022, 10]} />
                <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.25} />
              </mesh>
              <LedDot position={[0, 0.5, 0]} r={0.014} color={GOLD} />
            </group>
          ))}

          <mesh position={[0.19, 0.05, 0.12]} rotation={[0, Math.PI / 2, 0]}>
            <planeGeometry args={[0.11, 0.11]} />
            <meshBasicMaterial map={maps.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <mesh position={[-0.19, 0.05, 0.12]} rotation={[0, -Math.PI / 2, 0]}>
            <planeGeometry args={[0.11, 0.11]} />
            <meshBasicMaterial map={maps.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>

          <Bolt position={[-0.14, 0.3, 0.12]} />
          <Bolt position={[0.14, 0.3, 0.12]} />
          <Bolt position={[-0.14, 0.3, -0.1]} />
          <Bolt position={[0.14, 0.3, -0.1]} />
        </group>

        <HeroArm side={-1} motion={motion} />
        <HeroArm side={1} motion={motion} />
      </group>

      <HeroLeg side={-1} motion={motion} />
      <HeroLeg side={1} motion={motion} />
    </group>
  )
}
