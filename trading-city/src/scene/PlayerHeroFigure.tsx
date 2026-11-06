import { useMemo, useRef, type MutableRefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import { CanvasTexture, MathUtils, type Group, type Mesh, type MeshStandardMaterial } from 'three'

/**
 * Vault guest hero v3 — denser plating, orbit ring, energy field,
 * backpack winglets, HUD visor scan, cape flutter, locomotion limbs.
 */

const ARMOR = '#14141c'
const ARMOR_DARK = '#07070b'
const ARMOR_EDGE = '#22222c'
const METAL = '#34343e'
const ACCENT = '#5af0ff'
const ACCENT_DIM = '#1a9aaa'
const GOLD = '#ffd24a'
const GRAFFITI = '#f6f4ef'

export type PlayerHeroMotion = {
  step: number
  bobAmp: number
  groundSpeed: number
  grounded: boolean
  jumping: boolean
  sprinting: boolean
  turn: number
  /** Vertical velocity for thruster / squash. */
  velY?: number
}

function armor(roughness = 0.5, metalness = 0.72) {
  return {
    color: ARMOR,
    roughness,
    metalness,
    emissive: '#061820',
    emissiveIntensity: 0.14,
  }
}

function neon(color: string = ACCENT, intensity = 2.4) {
  return {
    color,
    emissive: color,
    emissiveIntensity: intensity,
    roughness: 0.15,
    metalness: 0.2,
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
      <meshStandardMaterial {...neon(color, 2.0)} />
    </mesh>
  )
}

function LedDot({
  position,
  r = 0.013,
  color = ACCENT,
}: {
  position: [number, number, number]
  r?: number
  color?: string
}) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[r, 12, 12]} />
      <meshStandardMaterial {...neon(color, 2.2)} />
    </mesh>
  )
}

function Bolt({ position }: { position: [number, number, number] }) {
  return (
    <mesh position={position}>
      <cylinderGeometry args={[0.01, 0.01, 0.014, 8]} />
      <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.24} />
    </mesh>
  )
}

function CrownMark({ scale = 1 }: { scale?: number }) {
  return (
    <group scale={scale}>
      <mesh position={[0, 0.01, 0]}>
        <boxGeometry args={[0.09, 0.024, 0.014]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.045, 0]}>
        <boxGeometry args={[0.022, 0.05, 0.014]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[-0.032, 0.035, 0]} rotation={[0, 0, 0.35]}>
        <boxGeometry args={[0.02, 0.044, 0.014]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0.032, 0.035, 0]} rotation={[0, 0, -0.35]}>
        <boxGeometry args={[0.02, 0.044, 0.014]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
    </group>
  )
}

const TEX_CACHE = new Map<string, CanvasTexture>()

function guestTexture(kind: 'pauldron' | 'unit' | 'pack' | 'chest') {
  const key = `guest-v3:${kind}`
  const hit = TEX_CACHE.get(key)
  if (hit) return hit
  const c = document.createElement('canvas')
  c.width = kind === 'pauldron' || kind === 'chest' ? 256 : 128
  c.height = kind === 'pauldron' || kind === 'chest' ? 256 : 128
  const ctx = c.getContext('2d')!
  ctx.clearRect(0, 0, c.width, c.height)
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  if (kind === 'pauldron') {
    ctx.strokeStyle = ACCENT
    ctx.lineWidth = 6
    ctx.strokeRect(18, 18, 220, 220)
    ctx.fillStyle = GRAFFITI
    ctx.font = 'bold 38px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('APEX', 128, 58)
    ctx.font = 'bold 34px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('TRUST', 128, 98)
    ctx.fillStyle = GOLD
    ctx.font = 'bold 40px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('VIP', 128, 148)
    ctx.fillStyle = ACCENT
    ctx.fillRect(48, 178, 160, 12)
    ctx.fillStyle = GOLD
    ctx.fillRect(72, 198, 112, 6)
    ctx.fillStyle = GRAFFITI
    ;[78, 108, 138, 168].forEach((x, i) => ctx.fillRect(x, 214, 5, 14 + i * 2))
  } else if (kind === 'pack') {
    ctx.fillStyle = ACCENT
    ctx.font = 'bold 36px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('VAULT', 64, 36)
    ctx.fillStyle = GOLD
    ctx.font = 'bold 52px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('01', 64, 88)
    ctx.fillStyle = ACCENT
    ctx.fillRect(24, 108, 80, 6)
  } else if (kind === 'chest') {
    ctx.strokeStyle = GOLD
    ctx.lineWidth = 5
    ctx.strokeRect(28, 40, 200, 176)
    ctx.fillStyle = ACCENT
    ctx.font = 'bold 44px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('GUEST', 128, 95)
    ctx.fillStyle = GOLD
    ctx.font = 'bold 64px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('01', 128, 168)
    ctx.fillStyle = ACCENT
    ctx.fillRect(64, 200, 128, 8)
  } else {
    ctx.fillStyle = GOLD
    ctx.font = 'bold 72px Impact, Haettenschweiler, sans-serif'
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
    const swing = m.step * (side < 0 ? 1 : -1) * (0.7 + m.bobAmp * 0.55)
    const hang = m.jumping ? -0.42 : -0.12
    const wantX = hang + swing
    const wantZ = -side * (0.18 + (m.sprinting ? 0.12 : 0)) + m.turn * side * -0.1
    ref.current.rotation.x = MathUtils.damp(ref.current.rotation.x, wantX, 16, dt)
    ref.current.rotation.z = MathUtils.damp(ref.current.rotation.z, wantZ, 14, dt)
    fore.current.rotation.x = MathUtils.damp(
      fore.current.rotation.x,
      -0.4 + Math.abs(swing) * 0.65 + (m.jumping ? 0.25 : 0),
      16,
      dt,
    )
  })

  return (
    <group ref={ref} position={[side * 0.38, 0.86, 0]} rotation={[-0.12, 0, -side * 0.2]}>
      <mesh>
        <sphereGeometry args={[0.085, 16, 14]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.82} roughness={0.34} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.095, 0.016, 8, 28]} />
        <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.22} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.11, 0.007, 6, 26]} />
        <meshStandardMaterial {...neon(GOLD, 1.4)} />
      </mesh>
      <LedDot position={[0, 0.025, 0.09]} r={0.014} color={GOLD} />

      {/* Layered upper arm */}
      <mesh position={[0, 0.19, 0]}>
        <boxGeometry args={[0.13, 0.38, 0.13]} />
        <meshStandardMaterial {...armor(0.46, 0.76)} />
      </mesh>
      <mesh position={[0, 0.19, 0]}>
        <boxGeometry args={[0.1, 0.35, 0.1]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.62} />
      </mesh>
      <mesh position={[side * 0.07, 0.19, 0]}>
        <boxGeometry args={[0.03, 0.3, 0.08]} />
        <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.35} />
      </mesh>
      <LedStrip position={[side * 0.07, 0.19, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.26, 0.018, 0.012]} />
      <LedStrip
        position={[side * 0.07, 0.19, 0]}
        rotation={[0, 0, Math.PI / 2]}
        size={[0.2, 0.01, 0.008]}
        color={GOLD}
      />
      <Bolt position={[side * 0.055, 0.08, 0.055]} />
      <Bolt position={[side * 0.055, 0.28, 0.055]} />

      <mesh position={[0, 0.4, 0]}>
        <sphereGeometry args={[0.065, 14, 12]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.85} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.4, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.074, 0.012, 8, 22]} />
        <meshStandardMaterial {...neon(ACCENT, 1.5)} />
      </mesh>

      <group ref={fore} position={[0, 0.4, 0]} rotation={[-0.42, 0, 0]}>
        <mesh position={[0, 0.17, 0]}>
          <boxGeometry args={[0.11, 0.34, 0.11]} />
          <meshStandardMaterial {...armor(0.44, 0.78)} />
        </mesh>
        <mesh position={[-side * 0.05, 0.17, 0]}>
          <boxGeometry args={[0.024, 0.26, 0.06]} />
          <meshStandardMaterial
            color="#04060a"
            metalness={0.4}
            roughness={0.6}
            emissive={ACCENT_DIM}
            emissiveIntensity={0.55}
          />
        </mesh>
        <LedStrip position={[side * 0.06, 0.17, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.26, 0.016, 0.01]} />
        <mesh position={[0, 0.32, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.06, 0.012, 8, 20]} />
          <meshStandardMaterial {...neon(GOLD, 1.6)} />
        </mesh>
        <group position={[0, 0.38, 0]}>
          <mesh>
            <boxGeometry args={[0.09, 0.06, 0.07]} />
            <meshStandardMaterial {...armor(0.4, 0.8)} />
          </mesh>
          <LedStrip position={[0, 0, 0.038]} size={[0.06, 0.014, 0.01]} color={GOLD} />
          {([-1, -0.33, 0.33, 1] as const).map((f) => (
            <mesh key={f} position={[f * 0.02, 0.065, 0.014]} rotation={[0.22, 0, f * 0.08]}>
              <boxGeometry args={[0.018, 0.11, 0.022]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.38} />
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
  const jet = useRef<MeshStandardMaterial>(null)

  useFrame(({ clock }, dt) => {
    if (!thigh.current || !shin.current) return
    const m = motion.current
    const swing = m.step * (side < 0 ? 1 : -1)
    const wantThigh = m.jumping ? -0.62 : swing * 0.85 * (0.45 + m.bobAmp)
    const wantShin = m.jumping ? 0.95 : Math.max(0, -swing) * 1.05 * m.bobAmp + 0.1
    thigh.current.rotation.x = MathUtils.damp(thigh.current.rotation.x, wantThigh, 18, dt)
    shin.current.rotation.x = MathUtils.damp(shin.current.rotation.x, wantShin, 18, dt)
    if (jet.current) {
      const power = m.jumping || m.sprinting ? 2.4 : 0.35
      jet.current.emissiveIntensity = power + Math.sin(clock.getElapsedTime() * 12) * 0.3
    }
  })

  return (
    <group position={[side * 0.14, 0.08, 0]}>
      <group ref={thigh}>
        <mesh position={[0, -0.17, 0.02]} rotation={[0.08, 0, side * 0.04]}>
          <boxGeometry args={[0.125, 0.36, 0.13]} />
          <meshStandardMaterial {...armor(0.5, 0.65)} />
        </mesh>
        <mesh position={[0, -0.17, 0.02]}>
          <boxGeometry args={[0.095, 0.32, 0.095]} />
          <meshStandardMaterial color={ARMOR_DARK} metalness={0.45} roughness={0.68} />
        </mesh>
        <LedStrip position={[side * 0.065, -0.14, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.2, 0.014, 0.01]} />
        <Bolt position={[side * 0.055, -0.05, 0.055]} />
        <Bolt position={[side * 0.055, -0.24, 0.055]} />

        <group ref={shin} position={[0, -0.36, 0.04]}>
          <mesh position={[0, -0.17, 0.02]} rotation={[0.18, 0, 0]}>
            <boxGeometry args={[0.11, 0.32, 0.12]} />
            <meshStandardMaterial {...armor(0.52, 0.62)} />
          </mesh>
          <LedStrip
            position={[side * 0.06, -0.15, 0.02]}
            rotation={[0, 0, Math.PI / 2]}
            size={[0.18, 0.012, 0.009]}
            color={GOLD}
          />
          {/* Armor boot + thruster sole */}
          <mesh position={[0, -0.36, 0.09]} rotation={[0.28, 0, 0]}>
            <boxGeometry args={[0.13, 0.09, 0.24]} />
            <meshStandardMaterial color={ARMOR_DARK} roughness={0.48} metalness={0.55} />
          </mesh>
          <mesh position={[0, -0.32, 0.18]} rotation={[0.28, 0, 0]}>
            <boxGeometry args={[0.12, 0.055, 0.09]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.32} />
          </mesh>
          <mesh position={[0, -0.4, 0.02]} rotation={[0.28, 0, 0]}>
            <boxGeometry args={[0.08, 0.03, 0.1]} />
            <meshStandardMaterial ref={jet} {...neon(ACCENT, 0.5)} />
          </mesh>
          <LedStrip position={[0, -0.34, 0.2]} size={[0.09, 0.014, 0.01]} />
        </group>
      </group>
    </group>
  )
}

export function PlayerHeroFigure({
  motion,
}: {
  motion: MutableRefObject<PlayerHeroMotion>
}) {
  const root = useRef<Group>(null)
  const torso = useRef<Group>(null)
  const head = useRef<Group>(null)
  const capeL = useRef<Group>(null)
  const capeR = useRef<Group>(null)
  const packGlow = useRef<MeshStandardMaterial>(null)
  const chestPulse = useRef<MeshStandardMaterial>(null)
  const visorScan = useRef<Mesh>(null)
  const holo = useRef<Group>(null)
  const thrusterL = useRef<MeshStandardMaterial>(null)
  const thrusterR = useRef<MeshStandardMaterial>(null)
  const orbit = useRef<Group>(null)
  const field = useRef<Mesh>(null)
  const maps = useMemo(
    () => ({
      pauldron: guestTexture('pauldron'),
      unit: guestTexture('unit'),
      pack: guestTexture('pack'),
      chest: guestTexture('chest'),
    }),
    [],
  )

  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime()
    const m = motion.current
    const velY = m.velY ?? 0
    if (root.current) {
      const landSquash = m.grounded && Math.abs(velY) < 0.1 ? 1 : 1
      const jumpStretch = m.jumping ? 1.06 : 1
      const breath = 1 + Math.sin(t * 1.5) * 0.01 * (1 - m.bobAmp * 0.4)
      const yScale = breath * jumpStretch * landSquash
      root.current.scale.set(1 / Math.sqrt(yScale), yScale, 1 / Math.sqrt(yScale))
    }
    if (torso.current) {
      const pitch = m.sprinting ? 0.12 : m.jumping ? -0.08 : m.groundSpeed * 0.015
      torso.current.rotation.x = MathUtils.damp(torso.current.rotation.x, pitch, 12, dt)
      torso.current.rotation.z = MathUtils.damp(torso.current.rotation.z, -m.turn * 0.08, 12, dt)
    }
    if (head.current) {
      head.current.rotation.y = Math.sin(t * 0.6) * 0.05 * (1 - m.bobAmp * 0.5)
      head.current.rotation.x = MathUtils.damp(
        head.current.rotation.x,
        m.sprinting ? 0.1 : Math.sin(t * 0.75) * 0.035,
        10,
        dt,
      )
    }
    const flutter = m.groundSpeed * 0.04 + (m.sprinting ? 0.15 : 0) + Math.sin(t * 6) * 0.04 * m.bobAmp
    if (capeL.current) capeL.current.rotation.x = MathUtils.damp(capeL.current.rotation.x, 0.2 + flutter, 8, dt)
    if (capeR.current) capeR.current.rotation.x = MathUtils.damp(capeR.current.rotation.x, 0.2 + flutter * 0.9, 8, dt)

    if (chestPulse.current) {
      chestPulse.current.emissiveIntensity =
        1.85 + Math.sin(t * 3.2) * 0.5 + (m.sprinting ? 0.65 : 0) + (m.jumping ? 0.4 : 0)
    }
    if (packGlow.current) {
      packGlow.current.emissiveIntensity =
        (m.sprinting ? 2.9 : m.jumping ? 2.3 : 1.35) + Math.sin(t * 5) * 0.4
    }
    const thrust = (m.sprinting || m.jumping ? 3.5 : 0.25) + Math.sin(t * 14) * 0.45
    if (thrusterL.current) thrusterL.current.emissiveIntensity = thrust
    if (thrusterR.current) thrusterR.current.emissiveIntensity = thrust
    if (visorScan.current) {
      visorScan.current.position.x = Math.sin(t * 2.4) * 0.08
    }
    if (holo.current) {
      holo.current.rotation.y = t * 1.4
      holo.current.position.y = 0.62 + Math.sin(t * 2.1) * 0.02
    }
    if (orbit.current) {
      orbit.current.rotation.y = t * 1.15
      orbit.current.rotation.z = Math.sin(t * 0.7) * 0.18
    }
    if (field.current) {
      const mat = field.current.material as { opacity?: number }
      if (mat.opacity != null) {
        mat.opacity = 0.18 + Math.sin(t * 2.2) * 0.08 + (m.sprinting ? 0.12 : 0)
      }
      const s = 1 + Math.sin(t * 1.8) * 0.06 + (m.jumping ? 0.12 : 0)
      field.current.scale.set(s, 1, s)
    }
  })

  return (
    <group ref={root} position={[0, 0.64, 0]} scale={1} frustumCulled={false}>
      <pointLight position={[0, 1.25, 0.6]} intensity={0.85} color="#9ef8ff" distance={4.6} />
      <pointLight position={[0, 0.95, -0.55]} intensity={0.55} color="#ffd24a" distance={3.4} />
      <pointLight position={[0, 0.4, -0.35]} intensity={0.42} color="#5af0ff" distance={2.6} />

      {/* Ground energy field */}
      <mesh ref={field} position={[0, -0.62, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.28, 0.52, 40]} />
        <meshBasicMaterial color={ACCENT} transparent opacity={0.22} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.615, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.18, 0.24, 32]} />
        <meshBasicMaterial color={GOLD} transparent opacity={0.35} depthWrite={false} toneMapped={false} />
      </mesh>

      <group ref={torso}>
        {/* Orbit halo around torso */}
        <group ref={orbit} position={[0, 0.58, 0]}>
          <mesh rotation={[Math.PI / 2.4, 0.2, 0]}>
            <torusGeometry args={[0.48, 0.012, 8, 48]} />
            <meshStandardMaterial {...neon(ACCENT, 1.6)} />
          </mesh>
          {([0, 1, 2] as const).map((i) => {
            const a = (i / 3) * Math.PI * 2
            return (
              <mesh key={i} position={[Math.cos(a) * 0.48, Math.sin(a) * 0.12, Math.sin(a) * 0.48]}>
                <sphereGeometry args={[0.028, 10, 10]} />
                <meshStandardMaterial {...neon(i === 1 ? GOLD : ACCENT, 2.2)} />
              </mesh>
            )
          })}
        </group>

        {/* Hip cage + skirt plates */}
        <mesh position={[0, 0.16, 0]}>
          <boxGeometry args={[0.36, 0.22, 0.28]} />
          <meshStandardMaterial {...armor(0.55, 0.65)} />
        </mesh>
        <LedStrip position={[0, 0.16, 0.15]} size={[0.22, 0.018, 0.012]} color={GOLD} />
        {([-1, 1] as const).map((side) => (
          <mesh key={side} position={[side * 0.19, 0.12, 0.02]} rotation={[0.15, 0, side * 0.2]}>
            <boxGeometry args={[0.11, 0.2, 0.045]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.4} />
          </mesh>
        ))}
        <mesh position={[0, 0.26, 0]}>
          <boxGeometry args={[0.4, 0.055, 0.32]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.8} roughness={0.3} />
        </mesh>
        {([-0.14, 0, 0.14] as const).map((x) => (
          <mesh key={x} position={[x, 0.26, 0.165]}>
            <boxGeometry args={[0.055, 0.045, 0.035]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.65} roughness={0.42} />
          </mesh>
        ))}

        {/* Heavy chest with bevel plates */}
        <mesh position={[0, 0.6, 0.02]}>
          <boxGeometry args={[0.52, 0.64, 0.38]} />
          <meshStandardMaterial {...armor(0.46, 0.74)} />
        </mesh>
        {([-1, 1] as const).map((side) => (
          <mesh key={side} position={[side * 0.29, 0.6, 0.02]}>
            <boxGeometry args={[0.09, 0.52, 0.32]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.34} />
          </mesh>
        ))}
        {/* Angular chest fins */}
        {([-1, 1] as const).map((side) => (
          <mesh key={`fin-${side}`} position={[side * 0.34, 0.72, 0.08]} rotation={[0.1, 0, side * 0.55]}>
            <boxGeometry args={[0.06, 0.28, 0.14]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.35} />
          </mesh>
        ))}
        <mesh position={[0, 0.6, 0]}>
          <boxGeometry args={[0.4, 0.54, 0.28]} />
          <meshStandardMaterial
            color={ARMOR_DARK}
            metalness={0.48}
            roughness={0.62}
            emissive={ACCENT_DIM}
            emissiveIntensity={0.48}
          />
        </mesh>
        {/* Spine */}
        <mesh position={[0, 0.6, -0.15]}>
          <boxGeometry args={[0.08, 0.56, 0.07]} />
          <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.28} />
        </mesh>
        {[0.42, 0.52, 0.62, 0.72].map((y) => (
          <mesh key={y} position={[0, y, -0.175]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.055, 0.01, 6, 16]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.8} roughness={0.26} />
          </mesh>
        ))}
        <LedStrip position={[0, 0.6, -0.19]} rotation={[Math.PI / 2, 0, 0]} size={[0.05, 0.44, 0.014]} />

        {/* Chest hero HUD */}
        <mesh position={[0, 0.64, 0.19]}>
          <boxGeometry args={[0.26, 0.2, 0.035]} />
          <meshStandardMaterial color={ARMOR_DARK} metalness={0.75} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.64, 0.215]}>
          <boxGeometry args={[0.2, 0.14, 0.014]} />
          <meshStandardMaterial ref={chestPulse} {...neon(ACCENT, 1.8)} />
        </mesh>
        <mesh position={[0, 0.64, 0.225]}>
          <planeGeometry args={[0.16, 0.12]} />
          <meshBasicMaterial map={maps.chest} transparent toneMapped={false} depthWrite={false} />
        </mesh>
        <LedStrip position={[-0.16, 0.76, 0.185]} size={[0.1, 0.016, 0.012]} color={GOLD} />
        <LedStrip position={[0.16, 0.76, 0.185]} size={[0.1, 0.016, 0.012]} color={GOLD} />
        <mesh position={[0, 0.5, 0.185]}>
          <boxGeometry args={[0.28, 0.018, 0.012]} />
          <meshStandardMaterial {...neon(GOLD, 1.5)} />
        </mesh>

        {/* Floating chest holo */}
        <group ref={holo} position={[0, 0.62, 0.28]} scale={0.35}>
          <mesh>
            <octahedronGeometry args={[0.12, 0]} />
            <meshBasicMaterial color={ACCENT} transparent opacity={0.75} toneMapped={false} />
          </mesh>
          <mesh>
            <octahedronGeometry args={[0.06, 0]} />
            <meshBasicMaterial color={GOLD} toneMapped={false} />
          </mesh>
        </group>

        {/* Collar rings */}
        <mesh position={[0, 0.92, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.24, 0.022, 8, 32]} />
          <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.22} />
        </mesh>
        <mesh position={[0, 0.92, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.27, 0.009, 6, 30]} />
          <meshStandardMaterial {...neon(GOLD, 1.25)} />
        </mesh>

        {/* Pauldrons */}
        {([-1, 1] as const).map((side) => (
          <group key={side} position={[side * 0.36, 0.98, 0.04]}>
            <mesh rotation={[0.14, side * 0.24, side * 0.48]}>
              <boxGeometry args={[0.32, 0.2, 0.36]} />
              <meshStandardMaterial {...armor(0.42, 0.8)} />
            </mesh>
            <mesh position={[0, 0.08, 0]} rotation={[0.14, side * 0.24, side * 0.48]}>
              <boxGeometry args={[0.34, 0.04, 0.38]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.82} roughness={0.28} />
            </mesh>
            <mesh position={[0, 0.1, 0.02]} rotation={[0.14, side * 0.24, side * 0.48]}>
              <boxGeometry args={[0.3, 0.016, 0.025]} />
              <meshStandardMaterial {...neon(GOLD, 1.35)} />
            </mesh>
            {/* Thruster pod on shoulder */}
            <mesh position={[side * 0.02, -0.02, -0.14]} rotation={[0.5, 0, side * 0.2]}>
              <cylinderGeometry args={[0.045, 0.055, 0.12, 10]} />
              <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.4} />
            </mesh>
            <LedStrip position={[side * 0.02, 0.0, 0.15]} size={[0.18, 0.016, 0.012]} />
            <LedStrip position={[side * 0.02, -0.05, 0.15]} size={[0.14, 0.012, 0.01]} color={GOLD} />
            <Bolt position={[side * 0.1, 0.05, 0.12]} />
            <Bolt position={[side * 0.1, -0.04, 0.12]} />
            <mesh position={[side * 0.16, 0.02, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <planeGeometry args={[0.24, 0.24]} />
              <meshBasicMaterial map={maps.pauldron} transparent toneMapped={false} depthWrite={false} />
            </mesh>
            <group position={[side * 0.165, 0.09, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <CrownMark scale={1.15} />
            </group>
          </group>
        ))}

        {/* Backpack + thrusters + winglets */}
        <group position={[0, 0.6, -0.3]}>
          <mesh>
            <boxGeometry args={[0.36, 0.48, 0.2]} />
            <meshStandardMaterial {...armor(0.48, 0.74)} />
          </mesh>
          <mesh position={[0, 0, -0.03]}>
            <boxGeometry args={[0.28, 0.38, 0.15]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.55} roughness={0.55} />
          </mesh>
          <mesh position={[0, -0.04, -0.13]}>
            <cylinderGeometry args={[0.075, 0.095, 0.11, 12]} />
            <meshStandardMaterial ref={packGlow} {...neon(ACCENT, 1.8)} />
          </mesh>
          {/* Dual exhaust */}
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.11, -0.2, -0.08]}>
              <mesh>
                <cylinderGeometry args={[0.038, 0.048, 0.11, 10]} />
                <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.35} />
              </mesh>
              <mesh position={[0, -0.08, 0]}>
                <cylinderGeometry args={[0.03, 0.034, 0.045, 10]} />
                <meshStandardMaterial ref={side < 0 ? thrusterL : thrusterR} {...neon(ACCENT, 0.4)} />
              </mesh>
            </group>
          ))}
          {/* Sweeping pack winglets */}
          {([-1, 1] as const).map((side) => (
            <mesh
              key={`wing-${side}`}
              position={[side * 0.22, 0.08, -0.02]}
              rotation={[0.15, side * -0.35, side * 0.55]}
            >
              <boxGeometry args={[0.22, 0.06, 0.14]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.8} roughness={0.28} />
            </mesh>
          ))}
          {([-1, 1] as const).map((side) => (
            <LedStrip
              key={`wing-led-${side}`}
              position={[side * 0.26, 0.1, 0]}
              rotation={[0.15, side * -0.35, side * 0.55]}
              size={[0.16, 0.014, 0.01]}
              color={GOLD}
            />
          ))}
          <mesh position={[0, 0.14, -0.11]}>
            <planeGeometry args={[0.2, 0.2]} />
            <meshBasicMaterial map={maps.pack} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <LedStrip position={[0, 0.22, -0.11]} size={[0.18, 0.016, 0.012]} color={GOLD} />
        </group>

        {/* Cape panels */}
        <group ref={capeL} position={[-0.2, 0.78, -0.1]}>
          <mesh rotation={[0.25, 0.12, -0.35]}>
            <boxGeometry args={[0.14, 0.48, 0.02]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.3} roughness={0.75} transparent opacity={0.9} />
          </mesh>
          <LedStrip position={[0, -0.1, 0.015]} rotation={[0.25, 0.12, -0.35]} size={[0.04, 0.3, 0.008]} color={GOLD} />
        </group>
        <group ref={capeR} position={[0.2, 0.78, -0.1]}>
          <mesh rotation={[0.25, -0.12, 0.35]}>
            <boxGeometry args={[0.14, 0.48, 0.02]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.3} roughness={0.75} transparent opacity={0.9} />
          </mesh>
          <LedStrip position={[0, -0.1, 0.015]} rotation={[0.25, -0.12, 0.35]} size={[0.04, 0.3, 0.008]} color={GOLD} />
        </group>

        <LedDot position={[-0.13, 1.02, 0.12]} r={0.014} color={GOLD} />
        <LedDot position={[0.13, 1.02, 0.12]} r={0.014} color={GOLD} />

        {/* Helmet v2 */}
        <group ref={head} position={[0, 1.12, 0.02]}>
          <mesh position={[0, -0.05, 0]}>
            <cylinderGeometry args={[0.055, 0.065, 0.12, 12]} />
            <meshStandardMaterial
              color={ARMOR_DARK}
              metalness={0.75}
              roughness={0.35}
              emissive={ACCENT_DIM}
              emissiveIntensity={0.55}
            />
          </mesh>
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[side * 0.04, -0.04, 0.02]}>
              <cylinderGeometry args={[0.012, 0.012, 0.11, 6]} />
              <meshStandardMaterial color={METAL} metalness={0.92} roughness={0.2} />
            </mesh>
          ))}

          <mesh position={[0, 0.17, 0.02]}>
            <boxGeometry args={[0.42, 0.36, 0.44]} />
            <meshStandardMaterial {...armor(0.4, 0.8)} />
          </mesh>
          <mesh position={[0, 0.17, 0.02]}>
            <boxGeometry args={[0.014, 0.34, 0.45]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.5} />
          </mesh>
          <mesh position={[0, 0.36, 0.02]}>
            <boxGeometry args={[0.38, 0.09, 0.4]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.32} />
          </mesh>
          {/* Crest ridge + crown gem */}
          <mesh position={[0, 0.42, 0.02]} rotation={[0.1, 0, 0]}>
            <boxGeometry args={[0.08, 0.1, 0.28]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.35} />
          </mesh>
          <mesh position={[0, 0.48, 0.06]}>
            <octahedronGeometry args={[0.04, 0]} />
            <meshStandardMaterial {...neon(GOLD, 2.4)} />
          </mesh>
          <mesh position={[0, 0.38, 0.22]}>
            <boxGeometry args={[0.2, 0.02, 0.03]} />
            <meshStandardMaterial {...neon(ACCENT, 1.8)} />
          </mesh>

          {/* Visor + scan bar */}
          <mesh position={[0, 0.16, 0.21]} rotation={[-0.32, 0, 0]}>
            <boxGeometry args={[0.36, 0.16, 0.07]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.75} roughness={0.28} />
          </mesh>
          <mesh position={[0, 0.16, 0.25]} rotation={[-0.32, 0, 0]}>
            <boxGeometry args={[0.3, 0.06, 0.025]} />
            <meshStandardMaterial {...neon(ACCENT, 2.5)} />
          </mesh>
          <mesh ref={visorScan} position={[0, 0.16, 0.265]} rotation={[-0.32, 0, 0]}>
            <boxGeometry args={[0.04, 0.05, 0.02]} />
            <meshStandardMaterial {...neon(GOLD, 2.5)} />
          </mesh>
          <LedDot position={[-0.08, 0.18, 0.255]} r={0.024} />
          <LedDot position={[0.08, 0.18, 0.255]} r={0.024} />
          <LedDot position={[0, 0.12, 0.26]} r={0.016} color={GOLD} />

          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.2, 0.16, 0.02]}>
              <mesh>
                <boxGeometry args={[0.028, 0.08, 0.18]} />
                <meshStandardMaterial color="#04060a" metalness={0.5} roughness={0.48} />
              </mesh>
              {([-0.055, -0.018, 0.018, 0.055] as const).map((z) => (
                <LedDot key={z} position={[side * 0.016, 0, z]} r={0.013} color={z > 0.04 ? GOLD : ACCENT} />
              ))}
            </group>
          ))}

          <LedStrip position={[0, 0.02, 0.17]} size={[0.18, 0.024, 0.014]} color={GOLD} />
          <mesh position={[0, 0.02, 0.15]}>
            <boxGeometry args={[0.22, 0.05, 0.1]} />
            <meshStandardMaterial
              color={ARMOR_DARK}
              metalness={0.75}
              roughness={0.35}
              emissive={ACCENT_DIM}
              emissiveIntensity={0.4}
            />
          </mesh>

          {/* Longer twin blades */}
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.11, 0.32, -0.15]} rotation={[0.48, 0, side * 0.28]}>
              <mesh position={[0, 0.28, 0]}>
                <boxGeometry args={[0.034, 0.58, 0.06]} />
                <meshStandardMaterial color={ARMOR_EDGE} metalness={0.84} roughness={0.28} />
              </mesh>
              {[0.1, 0.24, 0.38].map((y) => (
                <mesh key={y} position={[0, y, 0.012]}>
                  <boxGeometry args={[0.04, 0.06, 0.028]} />
                  <meshStandardMaterial color={ARMOR_DARK} />
                </mesh>
              ))}
              <mesh position={[0, 0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[0.038, 0.038, 0.024, 10]} />
                <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.22} />
              </mesh>
              <LedDot position={[0, 0.58, 0]} r={0.016} color={GOLD} />
              <mesh position={[0, 0.52, 0]}>
                <sphereGeometry args={[0.022, 10, 10]} />
                <meshBasicMaterial color={ACCENT} transparent opacity={0.55} toneMapped={false} />
              </mesh>
            </group>
          ))}

          <mesh position={[0.2, 0.05, 0.13]} rotation={[0, Math.PI / 2, 0]}>
            <planeGeometry args={[0.12, 0.12]} />
            <meshBasicMaterial map={maps.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <mesh position={[-0.2, 0.05, 0.13]} rotation={[0, -Math.PI / 2, 0]}>
            <planeGeometry args={[0.12, 0.12]} />
            <meshBasicMaterial map={maps.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>

          <Bolt position={[-0.15, 0.32, 0.13]} />
          <Bolt position={[0.15, 0.32, 0.13]} />
          <Bolt position={[-0.15, 0.32, -0.1]} />
          <Bolt position={[0.15, 0.32, -0.1]} />
        </group>

        <HeroArm side={-1} motion={motion} />
        <HeroArm side={1} motion={motion} />
      </group>

      <HeroLeg side={-1} motion={motion} />
      <HeroLeg side={1} motion={motion} />
    </group>
  )
}
