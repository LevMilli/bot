import { useMemo, useRef, type RefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import { CanvasTexture, Matrix4, Quaternion, Vector3, type Group, type MeshStandardMaterial } from 'three'
import type { BotPose } from '../data/botPose'
import { mouseHand, typingHand } from './deskReach'

/** Shared canvas decals — one texture per kind/mark, not per bot instance. */
const TEX_CACHE = new Map<string, CanvasTexture>()

/** Matte gunmetal armor — used-future black, not glossy. */
const ARMOR = '#121218'
const ARMOR_DARK = '#08080c'
const ARMOR_EDGE = '#1c1c24'
const METAL = '#2a2a32'
const PURPLE = '#c44dff'
const PURPLE_DIM = '#7a2fb8'
const GRAFFITI = '#f2f2f0'

function armor(roughness = 0.58, metalness = 0.62) {
  return {
    color: ARMOR,
    roughness,
    metalness,
    emissive: '#0a0512',
    emissiveIntensity: 0.08,
  }
}

function neon(intensity = 1.4) {
  return {
    color: PURPLE,
    emissive: PURPLE,
    emissiveIntensity: intensity,
    roughness: 0.25,
    metalness: 0.2,
    toneMapped: false as const,
  }
}

/** Recessed rectangular LED strip. */
function LedStrip({
  position,
  rotation,
  size = [0.12, 0.018, 0.012],
}: {
  position: [number, number, number]
  rotation?: [number, number, number]
  size?: [number, number, number]
}) {
  return (
    <mesh position={position} rotation={rotation}>
      <boxGeometry args={size} />
      <meshStandardMaterial {...neon(1.55)} />
    </mesh>
  )
}

/** Small rivet / bolt head. */
function Bolt({ position }: { position: [number, number, number] }) {
  return (
    <mesh position={position}>
      <cylinderGeometry args={[0.008, 0.008, 0.01, 8]} />
      <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.3} />
    </mesh>
  )
}

/** Three-point crown (faction mark) as real geometry. */
function CrownMark({ scale = 1 }: { scale?: number }) {
  return (
    <group scale={scale}>
      <mesh position={[0, 0.01, 0]}>
        <boxGeometry args={[0.07, 0.02, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.035, 0]}>
        <boxGeometry args={[0.018, 0.04, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[-0.028, 0.028, 0]} rotation={[0, 0, 0.35]}>
        <boxGeometry args={[0.016, 0.036, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[0.028, 0.028, 0]} rotation={[0, 0, -0.35]}>
        <boxGeometry args={[0.016, 0.036, 0.012]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
    </group>
  )
}

/** Kill/trade tally: four bars + diagonal. */
function TallyMark() {
  return (
    <group>
      {([-0.03, -0.01, 0.01, 0.03] as const).map((x) => (
        <mesh key={x} position={[x, 0, 0]}>
          <boxGeometry args={[0.008, 0.06, 0.006]} />
          <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0, 0, 0.002]} rotation={[0, 0, -0.7]}>
        <boxGeometry args={[0.008, 0.072, 0.006]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
    </group>
  )
}

function LedDot({ position, r = 0.012 }: { position: [number, number, number]; r?: number }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[r, 10, 10]} />
      <meshStandardMaterial {...neon(1.8)} />
    </mesh>
  )
}

function graffitiTexture(kind: 'pauldron' | 'unit', mark: string) {
  const key = `${kind}:${mark}`
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
    ctx.beginPath()
    ctx.moveTo(128, 48)
    ctx.lineTo(98, 88)
    ctx.lineTo(108, 88)
    ctx.lineTo(108, 108)
    ctx.lineTo(148, 108)
    ctx.lineTo(148, 88)
    ctx.lineTo(158, 88)
    ctx.closePath()
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(98, 88)
    ctx.lineTo(78, 58)
    ctx.lineTo(92, 88)
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(158, 88)
    ctx.lineTo(178, 58)
    ctx.lineTo(164, 88)
    ctx.fill()
    ctx.font = 'bold 36px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('PIMPS', 128, 155)
    ctx.font = 'bold 34px Impact, Haettenschweiler, sans-serif'
    ctx.fillText('ONLY', 128, 195)
    ctx.fillRect(95, 210, 4, 18)
    ctx.fillRect(118, 208, 3, 22)
    ctx.fillRect(145, 212, 4, 14)
    ctx.fillRect(162, 210, 3, 16)
  } else {
    ctx.font = 'bold 72px Impact, Haettenschweiler, sans-serif'
    ctx.fillText(mark.slice(0, 2), 64, 68)
  }

  const tex = new CanvasTexture(c)
  tex.needsUpdate = true
  TEX_CACHE.set(key, tex)
  return tex
}

/** Mechanical multi-finger hand for desk work. */
function MechGrip({ work = false, gripRef }: { work?: boolean; gripRef?: RefObject<Group | null> }) {
  const own = useRef<Group>(null)
  const ref = gripRef ?? own
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!ref.current || work) return
    ref.current.rotation.z = Math.sin(t * 2.8) * 0.12
    ref.current.rotation.x = Math.sin(t * 1.9) * 0.08
  })
  return (
    <group ref={ref}>
      <mesh>
        <boxGeometry args={[0.07, 0.05, 0.055]} />
        <meshStandardMaterial {...armor(0.5, 0.7)} />
      </mesh>
      <LedStrip position={[0, 0, 0.03]} size={[0.05, 0.01, 0.008]} />
      {([-1, 0, 1] as const).map((side) => (
        <mesh key={side} position={[side * 0.022, 0.055, 0.01]} rotation={[0.15, 0, side * 0.12]}>
          <boxGeometry args={[0.018, 0.09, 0.022]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.45} />
        </mesh>
      ))}
    </group>
  )
}

type ArmPose = BotPose

const UPPER = 0.34
const FORE = 0.34
const _shoulder = new Vector3()
const _target = new Vector3()
const _delta = new Vector3()
const _dir = new Vector3()
const _bend = new Vector3()
const _elbow = new Vector3()
const _pole = new Vector3()
const _fingers = new Vector3()
const _up = new Vector3()
const _x = new Vector3()
const _z = new Vector3()
const _parentQ = new Quaternion()
const _worldQ = new Quaternion()
const _basis = new Matrix4()

function aimY(dir: Vector3, hint: Vector3, out: Quaternion) {
  _z.copy(dir).normalize()
  _dir.copy(dir).normalize()
  _x.crossVectors(hint, _dir)
  if (_x.lengthSq() < 1e-8) _x.set(1, 0, 0).cross(_dir)
  _x.normalize()
  _z.crossVectors(_x, _dir).normalize()
  _basis.makeBasis(_x, _dir, _z)
  return out.setFromRotationMatrix(_basis)
}

function IndustrialArm({
  side,
  pose,
  work = false,
}: {
  side: -1 | 1
  pose: ArmPose
  work?: boolean
}) {
  const ref = useRef<Group>(null)
  const fore = useRef<Group>(null)
  const grip = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!ref.current) return

    if (work && fore.current && ref.current.parent) {
      const pace = pose === 'losing' ? 0.55 : pose === 'winning' ? 1.15 : pose === 'trading' ? 1.05 : 0.8
      const goal = side === -1 ? typingHand(t, pace) : mouseHand(t)
      ref.current.updateWorldMatrix(true, false)
      ref.current.getWorldPosition(_shoulder)
      _target.set(goal.x, goal.y, goal.z)
      if (side === -1) _target.x = Math.min(_target.x, -0.08)
      else _target.x = Math.max(_target.x, 0.22)

      _delta.copy(_target).sub(_shoulder)
      let dist = _delta.length()
      const max = UPPER + FORE - 0.001
      const min = Math.abs(UPPER - FORE) + 0.001
      if (dist > max) {
        _delta.multiplyScalar(max / dist)
        dist = max
      } else if (dist < min) {
        _delta.multiplyScalar(min / Math.max(dist, 1e-6))
        dist = min
      }
      _dir.copy(_delta).normalize()
      const cosA = Math.min(1, Math.max(-1, (UPPER * UPPER + dist * dist - FORE * FORE) / (2 * UPPER * dist)))
      const sinA = Math.sqrt(Math.max(0, 1 - cosA * cosA))
      _pole.set(side * -0.45, 1, 0.55)
      _bend.copy(_pole).addScaledVector(_dir, -_pole.dot(_dir))
      if (_bend.lengthSq() < 1e-8) _bend.set(0, 0, 1)
      _bend.normalize()
      _elbow.copy(_shoulder).addScaledVector(_dir, cosA * UPPER).addScaledVector(_bend, sinA * UPPER)

      const parent = ref.current.parent
      parent.updateWorldMatrix(true, false)
      parent.getWorldQuaternion(_parentQ)
      aimY(_elbow.clone().sub(_shoulder), _bend, _worldQ)
      ref.current.quaternion.copy(_parentQ).invert().multiply(_worldQ)

      const upperWorld = _worldQ.clone()
      aimY(_target.clone().sub(_elbow), _bend, _worldQ)
      fore.current.quaternion.copy(upperWorld).invert().multiply(_worldQ)

      if (grip.current) {
        const down = side === -1 ? -0.34 : -0.16
        _fingers.set(side * 0.08, down, -1).normalize()
        _up.set(0, 1, 0)
        aimY(_fingers, _up, _worldQ)
        const foreWorld = upperWorld
        fore.current.getWorldQuaternion(foreWorld)
        grip.current.quaternion.copy(foreWorld).invert().multiply(_worldQ)
      }
      return
    }

    if (pose === 'trading') {
      const type = Math.sin(t * 7.2 + side * 1.7) * 0.07
      ref.current.rotation.z = -side * 0.1 + Math.sin(t * 1.4 + side) * 0.04
      ref.current.rotation.x = -2.2 + Math.sin(t * 0.95) * 0.05
      if (fore.current) fore.current.rotation.x = -0.05 + type
      return
    }
    if (pose === 'researching') {
      const scan = Math.sin(t * 1.8 + side) * 0.1
      ref.current.rotation.z = -side * 0.18 + Math.sin(t * 1.2 + side) * 0.04
      ref.current.rotation.x = -1.85 + scan
      if (fore.current) fore.current.rotation.x = -0.35 + Math.sin(t * 2.4 + side) * 0.1
      return
    }
    if (pose === 'winning') {
      const lift = Math.sin(t * 2.4 + side) * 0.1
      ref.current.rotation.z = -side * 1.05 - side * lift
      ref.current.rotation.x = -0.22 + Math.sin(t * 1.1 + side) * 0.06
      if (fore.current) fore.current.rotation.x = -0.35 + Math.sin(t * 2.6 + side) * 0.08
      return
    }
    if (pose === 'losing') {
      const sag = Math.sin(t * 1.35 + side) * 0.06
      ref.current.rotation.z = -side * 0.35 + sag
      ref.current.rotation.x = -1.15 + Math.sin(t * 0.9 + side) * 0.07
      if (fore.current) fore.current.rotation.x = -0.55 + Math.sin(t * 2.2 + side) * 0.1
      return
    }
    const breath = Math.sin(t * 1.25 + side) * 0.07
    ref.current.rotation.z = -side * 0.55 + breath
    ref.current.rotation.x = -0.85 + Math.sin(t * 0.8 + side) * 0.08
    if (fore.current) fore.current.rotation.x = -0.5 + Math.sin(t * 2.1 + side * 1.3) * 0.1
  })

  const trading = pose === 'trading'
  return (
    <group
      ref={ref}
      position={[side * 0.34, 0.78, 0]}
      rotation={[trading ? -2.2 : -0.85, 0, trading ? -side * 0.1 : -side * 0.55]}
    >
      {/* Shoulder ball + ring */}
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[0.07, 16, 14]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.75} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.078, 0.012, 8, 24]} />
        <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.28} />
      </mesh>
      <LedDot position={[0, 0.02, 0.075]} r={0.01} />

      {/* Upper arm plating */}
      <mesh position={[0, 0.17, 0]}>
        <boxGeometry args={[0.1, 0.32, 0.1]} />
        <meshStandardMaterial {...armor(0.55, 0.68)} />
      </mesh>
      <mesh position={[0, 0.17, 0]}>
        <boxGeometry args={[0.085, 0.3, 0.085]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.65} />
      </mesh>
      <LedStrip position={[side * 0.052, 0.17, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.2, 0.014, 0.01]} />
      <Bolt position={[side * 0.045, 0.08, 0.04]} />
      <Bolt position={[side * 0.045, 0.22, 0.04]} />

      {/* Elbow joint */}
      <mesh position={[0, 0.34, 0]}>
        <sphereGeometry args={[0.055, 14, 12]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.8} roughness={0.35} />
      </mesh>
      <mesh position={[0, 0.34, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.062, 0.01, 8, 22]} />
        <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.25} />
      </mesh>
      <LedDot position={[0, 0.34, 0.065]} r={0.009} />

      <group ref={fore} position={[0, 0.34, 0]} rotation={[trading ? -0.05 : -0.5, 0, 0]}>
        <mesh position={[0, 0.15, 0]}>
          <boxGeometry args={[0.09, 0.3, 0.09]} />
          <meshStandardMaterial {...armor(0.52, 0.7)} />
        </mesh>
        {/* Exposed mechanical guts on inner face */}
        <mesh position={[-side * 0.04, 0.15, 0]}>
          <boxGeometry args={[0.02, 0.22, 0.05]} />
          <meshStandardMaterial color="#050508" metalness={0.4} roughness={0.7} emissive={PURPLE_DIM} emissiveIntensity={0.35} />
        </mesh>
        <LedStrip position={[side * 0.048, 0.15, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.22, 0.014, 0.01]} />
        {/* Tally marks on outer forearm — raised white bars */}
        <group position={[side * 0.052, 0.14, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
          <TallyMark />
        </group>
        <mesh position={[0, 0.32, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.048, 0.008, 8, 18]} />
          <meshStandardMaterial {...neon(1.2)} />
        </mesh>
        <group position={[0, 0.34, 0]}>
          <MechGrip work={work} gripRef={grip} />
        </group>
      </group>
    </group>
  )
}

function SeatedLegs() {
  return (
    <>
      {([-1, 1] as const).map((side) => (
        <group key={side}>
          <mesh position={[side * 0.14, 0.22, 0.02]} rotation={[-Math.PI / 2, 0, side * 0.04]}>
            <boxGeometry args={[0.11, 0.28, 0.12]} />
            <meshStandardMaterial {...armor(0.6, 0.55)} />
          </mesh>
          <LedStrip position={[side * 0.14, 0.22, 0.08]} size={[0.06, 0.012, 0.008]} />
          <mesh position={[side * 0.14, -0.05, -0.14]} rotation={[0.15, 0, 0]}>
            <boxGeometry args={[0.1, 0.42, 0.1]} />
            <meshStandardMaterial {...armor(0.62, 0.55)} />
          </mesh>
          <mesh position={[side * 0.14, -0.28, -0.02]} rotation={[0.2, 0, 0]}>
            <boxGeometry args={[0.11, 0.07, 0.18]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.6} roughness={0.55} />
          </mesh>
        </group>
      ))}
    </>
  )
}

/**
 * Purple industrial cyberpunk trader bot — mimics the user reference photos.
 * Gated behind botRemodelGate; keep classic BotFigure until approved.
 */
export function IndustrialBotFigure({
  pose = 'waiting',
  seated = true,
  deskWork = false,
  seed = 0,
  unitMark,
  lite = false,
}: {
  pose?: BotPose
  seated?: boolean
  deskWork?: boolean
  seed?: number
  /** Alphanumeric unit ID painted on helmet (refs use "22"). */
  unitMark?: string
  /** Low-poly silhouette for distant plaza car riders — no lights / heavy decals. */
  lite?: boolean
}) {
  const body = useRef<Group>(null)
  const torso = useRef<Group>(null)
  const head = useRef<Group>(null)
  const legs = useRef<Group>(null)
  const stripPulse = useRef<MeshStandardMaterial>(null)
  const mark = unitMark ?? String(20 + (Math.abs(Math.floor(seed * 10)) % 80)).padStart(2, '0')
  const maps = useMemo(
    () =>
      lite
        ? null
        : {
            pauldron: graffitiTexture('pauldron', mark),
            unit: graffitiTexture('unit', mark),
          },
    [mark, lite],
  )
  const anchor: [number, number, number] = deskWork ? [0, 0.49, 0.86] : seated ? [0, 0, 0.42] : [0, 0.28, 0]
  const phase = seed * 1.37

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() + phase
    if (body.current) {
      let bob = Math.sin(t * 1.35) * 0.014
      if (pose === 'trading') bob = Math.sin(t * 1.85) * 0.018
      if (pose === 'winning') bob = Math.sin(t * 2.4) * 0.022
      if (pose === 'losing') bob = Math.sin(t * 0.95) * 0.01
      if (pose === 'researching') bob = Math.sin(t * 1.45) * 0.013
      body.current.position.y = anchor[1] + bob
      const sway = deskWork ? 0.005 : 0.018
      body.current.position.x = anchor[0] + Math.sin(t * 0.62) * sway
      body.current.rotation.y = Math.sin(t * 0.48) * (deskWork ? 0.025 : 0.08)
      body.current.rotation.z = Math.sin(t * 0.78) * (deskWork ? 0 : 0.022)
      const breathe = deskWork ? 1 : 1 + Math.sin(t * 1.45) * 0.012
      body.current.scale.set(1, breathe, 1)
    }
    if (legs.current && !seated && !deskWork) {
      const shift = Math.sin(t * 0.9) * 0.035
      legs.current.rotation.z = shift
      legs.current.position.x = -shift * 0.15
    }
    if (torso.current) {
      if (pose === 'losing') torso.current.rotation.x = deskWork ? 0.08 : 0.24
      else if (pose === 'researching') torso.current.rotation.x = -0.1 + Math.sin(t * 1.4) * 0.025
      else if (pose === 'winning') torso.current.rotation.x = -0.05
      else torso.current.rotation.x = 0
    }
    if (head.current) {
      const look = Math.sin(t * 0.62) * 0.18
      const nod = Math.sin(t * 0.48 + 0.6) * 0.05
      const tilt = Math.sin(t * 0.8) * 0.03
      const deskNod = deskWork ? -0.12 : 0
      if (pose === 'losing') {
        head.current.rotation.x = (deskWork ? 0.04 : 0.18) + nod
        head.current.rotation.y = look * 0.5
      } else if (pose === 'researching') {
        head.current.rotation.y = look
        head.current.rotation.x = -0.06 + nod + deskNod
      } else if (pose === 'trading') {
        head.current.rotation.x = -0.08 + nod + deskNod
        head.current.rotation.y = look * 0.65
      } else if (pose === 'winning') {
        head.current.rotation.x = -0.05 + nod + deskNod
        head.current.rotation.y = look
      } else {
        head.current.rotation.x = nod + deskNod
        head.current.rotation.y = look
      }
      head.current.rotation.z = tilt
    }
    if (stripPulse.current) {
      stripPulse.current.emissiveIntensity = 1.35 + Math.sin(t * 2.6) * 0.35
    }
  })

  // Plaza car riders: black+purple silhouette only — no point lights / Text / heavy plates.
  if (lite) {
    return (
      <group ref={body} position={anchor}>
        <mesh position={[0, 0.55, 0]}>
          <boxGeometry args={[0.36, 0.5, 0.26]} />
          <meshStandardMaterial {...armor(0.55, 0.65)} />
        </mesh>
        <mesh position={[0, 0.55, 0.14]}>
          <boxGeometry args={[0.2, 0.02, 0.01]} />
          <meshStandardMaterial {...neon(1.2)} />
        </mesh>
        <group ref={head} position={[0, 1.0, 0.02]}>
          <mesh position={[0, 0.14, 0]}>
            <boxGeometry args={[0.28, 0.26, 0.3]} />
            <meshStandardMaterial {...armor(0.5, 0.7)} />
          </mesh>
          <LedDot position={[-0.05, 0.14, 0.16]} r={0.016} />
          <LedDot position={[0.05, 0.14, 0.16]} r={0.016} />
          <mesh position={[-0.07, 0.36, -0.08]} rotation={[0.3, 0, -0.15]}>
            <boxGeometry args={[0.02, 0.28, 0.035]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.35} />
          </mesh>
          <mesh position={[0.07, 0.36, -0.08]} rotation={[0.3, 0, 0.15]}>
            <boxGeometry args={[0.02, 0.28, 0.035]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.35} />
          </mesh>
        </group>
        {([-1, 1] as const).map((side) => (
          <mesh key={side} position={[side * 0.28, 0.7, 0]} rotation={[0.2, 0, side * 0.4]}>
            <boxGeometry args={[0.12, 0.4, 0.1]} />
            <meshStandardMaterial {...armor(0.55, 0.6)} />
          </mesh>
        ))}
        {seated || deskWork ? (
          <SeatedLegs />
        ) : (
          <group ref={legs}>
            {([-1, 1] as const).map((side) => (
              <mesh key={side} position={[side * 0.12, -0.12, 0.02]}>
                <boxGeometry args={[0.09, 0.32, 0.09]} />
                <meshStandardMaterial {...armor(0.6, 0.55)} />
              </mesh>
            ))}
          </group>
        )}
      </group>
    )
  }

  return (
    <group ref={body} position={anchor}>
      <group ref={torso}>
        {/* Hip block */}
        <mesh position={[0, deskWork ? 0.3 : 0.14, deskWork ? 0.04 : 0]}>
          <boxGeometry args={[0.28, 0.16, 0.22]} />
          <meshStandardMaterial {...armor(0.6, 0.58)} />
        </mesh>

        {/* Torso core — wider heavy chest cage */}
        <mesh position={[0, 0.55, 0.02]}>
          <boxGeometry args={[0.44, 0.54, 0.32]} />
          <meshStandardMaterial {...armor(0.55, 0.65)} />
        </mesh>
        {/* Side armor plates */}
        {([-1, 1] as const).map((side) => (
          <mesh key={side} position={[side * 0.24, 0.55, 0.02]}>
            <boxGeometry args={[0.06, 0.4, 0.26]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.4} />
          </mesh>
        ))}
        {/* Inner chassis glow */}
        <mesh position={[0, 0.55, 0]}>
          <boxGeometry args={[0.34, 0.46, 0.22]} />
          <meshStandardMaterial color={ARMOR_DARK} metalness={0.45} roughness={0.7} emissive={PURPLE_DIM} emissiveIntensity={0.28} />
        </mesh>
        {/* Mechanical spine */}
        <mesh position={[0, 0.55, -0.12]}>
          <boxGeometry args={[0.06, 0.48, 0.05]} />
          <meshStandardMaterial color={METAL} metalness={0.8} roughness={0.35} />
        </mesh>
        {[0.38, 0.48, 0.58, 0.68].map((y) => (
          <mesh key={y} position={[0, y, -0.14]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.045, 0.008, 6, 16]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.3} />
          </mesh>
        ))}
        <LedStrip position={[0, 0.55, -0.155]} rotation={[Math.PI / 2, 0, 0]} size={[0.04, 0.36, 0.01]} />

        {/* Chest LED strips */}
        <LedStrip position={[-0.14, 0.62, 0.15]} size={[0.08, 0.014, 0.01]} />
        <LedStrip position={[0.14, 0.62, 0.15]} size={[0.08, 0.014, 0.01]} />
        <mesh position={[0, 0.48, 0.15]}>
          <boxGeometry args={[0.2, 0.014, 0.01]} />
          <meshStandardMaterial ref={stripPulse} {...neon(1.4)} />
        </mesh>

        {/* Shoulder ring frame */}
        <mesh position={[0, 0.82, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.2, 0.018, 8, 28]} />
          <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.28} />
        </mesh>

        {/* Heavy angular pauldrons — graffiti canvas */}
        {([-1, 1] as const).map((side) => (
          <group key={side} position={[side * 0.32, 0.88, 0.04]}>
            <mesh rotation={[0.12, side * 0.2, side * 0.42]}>
              <boxGeometry args={[0.26, 0.16, 0.3]} />
              <meshStandardMaterial {...armor(0.48, 0.72)} />
            </mesh>
            {/* Raised rim */}
            <mesh position={[0, 0.06, 0]} rotation={[0.12, side * 0.2, side * 0.42]}>
              <boxGeometry args={[0.28, 0.03, 0.32]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.35} />
            </mesh>
            <LedStrip position={[side * 0.02, 0.0, 0.12]} size={[0.14, 0.014, 0.01]} />
            <LedStrip position={[side * 0.02, -0.04, 0.12]} size={[0.1, 0.01, 0.008]} />
            <Bolt position={[side * 0.08, 0.05, 0.1]} />
            <Bolt position={[side * 0.08, -0.03, 0.1]} />
            <Bolt position={[side * 0.08, 0.05, -0.06]} />
            {/* Crown + PIMPS ONLY — canvas decal (no troika Text / CDN fonts). */}
            <mesh position={[side * 0.135, 0.02, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <planeGeometry args={[0.2, 0.2]} />
              <meshBasicMaterial map={maps!.pauldron} transparent toneMapped={false} depthWrite={false} />
            </mesh>
            <group position={[side * 0.138, 0.07, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <CrownMark scale={0.9} />
            </group>
          </group>
        ))}

        {/* Collar LEDs */}
        <LedDot position={[-0.1, 0.92, 0.08]} r={0.01} />
        <LedDot position={[0.1, 0.92, 0.08]} r={0.01} />

        {/* ── Head / helmet ── */}
        <group ref={head} position={[0, 1.02, 0.02]}>
          {/* Neck stack: pistons + cables + glow */}
          <mesh position={[0, -0.06, 0]}>
            <cylinderGeometry args={[0.045, 0.055, 0.1, 12]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.4} emissive={PURPLE_DIM} emissiveIntensity={0.45} />
          </mesh>
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[side * 0.035, -0.05, 0.02]}>
              <cylinderGeometry args={[0.01, 0.01, 0.09, 6]} />
              <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.25} />
            </mesh>
          ))}
          <mesh position={[0, -0.05, -0.03]}>
            <cylinderGeometry args={[0.012, 0.012, 0.08, 6]} />
            <meshStandardMaterial color="#1a1020" metalness={0.4} roughness={0.6} emissive={PURPLE} emissiveIntensity={0.5} />
          </mesh>
          {/* Cable bundles */}
          <mesh position={[-0.04, -0.04, -0.02]} rotation={[0.2, 0, 0.3]}>
            <cylinderGeometry args={[0.008, 0.008, 0.07, 6]} />
            <meshStandardMaterial color="#0a0a0e" roughness={0.85} />
          </mesh>
          <mesh position={[0.04, -0.04, -0.02]} rotation={[0.2, 0, -0.3]}>
            <cylinderGeometry args={[0.008, 0.008, 0.07, 6]} />
            <meshStandardMaterial color="#0a0a0e" roughness={0.85} />
          </mesh>

          {/* Helmet main shell — blocky tactical */}
          <mesh position={[0, 0.15, 0.02]}>
            <boxGeometry args={[0.36, 0.3, 0.38]} />
            <meshStandardMaterial {...armor(0.48, 0.72)} />
          </mesh>
          {/* Segment seams */}
          <mesh position={[0, 0.15, 0.02]}>
            <boxGeometry args={[0.01, 0.28, 0.39]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.55} />
          </mesh>
          {/* Crown plate */}
          <mesh position={[0, 0.3, 0.02]}>
            <boxGeometry args={[0.32, 0.07, 0.34]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.7} roughness={0.4} />
          </mesh>
          {/* Visor slope */}
          <mesh position={[0, 0.13, 0.18]} rotation={[-0.4, 0, 0]}>
            <boxGeometry args={[0.32, 0.17, 0.07]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.65} roughness={0.35} />
          </mesh>

          {/* Front eye dots — three-dot face from hero ref */}
          <LedDot position={[-0.06, 0.15, 0.22]} r={0.02} />
          <LedDot position={[0.06, 0.15, 0.22]} r={0.02} />
          <LedDot position={[0, 0.1, 0.225]} r={0.014} />

          {/* Side four-dot sensor bay (both sides) */}
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.165, 0.14, 0.02]}>
              <mesh>
                <boxGeometry args={[0.02, 0.06, 0.14]} />
                <meshStandardMaterial color="#050508" metalness={0.5} roughness={0.5} />
              </mesh>
              {([-0.045, -0.015, 0.015, 0.045] as const).map((z) => (
                <LedDot key={z} position={[side * 0.012, 0, z]} r={0.011} />
              ))}
            </group>
          ))}

          {/* Chin / jaw purple strip */}
          <LedStrip position={[0, 0.02, 0.14]} size={[0.14, 0.02, 0.012]} />
          <mesh position={[0, 0.02, 0.12]}>
            <boxGeometry args={[0.18, 0.04, 0.08]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.4} emissive={PURPLE_DIM} emissiveIntensity={0.3} />
          </mesh>

          {/* Twin long blade antennae from rear-top (ref signature) */}
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.09, 0.28, -0.12]} rotation={[0.42, 0, side * 0.22]}>
              <mesh position={[0, 0.2, 0]}>
                <boxGeometry args={[0.028, 0.42, 0.05]} />
                <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.32} />
              </mesh>
              {/* Industrial cut-outs */}
              {[0.08, 0.18, 0.28].map((y) => (
                <mesh key={y} position={[0, y, 0.008]}>
                  <boxGeometry args={[0.032, 0.05, 0.022]} />
                  <meshStandardMaterial color={ARMOR_DARK} />
                </mesh>
              ))}
              <mesh position={[0, 0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[0.03, 0.03, 0.02, 10]} />
                <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.28} />
              </mesh>
              <Bolt position={[0, 0.02, 0.025]} />
              <LedDot position={[0, 0.42, 0]} r={0.01} />
            </group>
          ))}

          {/* Unit mark — canvas planes only (CSP-safe; no per-bot lights). */}
          <mesh position={[0.17, 0.05, 0.1]} rotation={[0, Math.PI / 2, 0]}>
            <planeGeometry args={[0.1, 0.1]} />
            <meshBasicMaterial map={maps!.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <mesh position={[-0.17, 0.05, 0.1]} rotation={[0, -Math.PI / 2, 0]}>
            <planeGeometry args={[0.1, 0.1]} />
            <meshBasicMaterial map={maps!.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <mesh position={[0, 0.14, -0.18]} rotation={[0, Math.PI, 0]}>
            <planeGeometry args={[0.14, 0.14]} />
            <meshBasicMaterial map={maps!.unit} transparent opacity={0.45} toneMapped={false} depthWrite={false} />
          </mesh>

          {/* Helmet bolts */}
          <Bolt position={[-0.12, 0.26, 0.1]} />
          <Bolt position={[0.12, 0.26, 0.1]} />
          <Bolt position={[-0.12, 0.26, -0.08]} />
          <Bolt position={[0.12, 0.26, -0.08]} />
        </group>

        <IndustrialArm side={-1} pose={pose} work={deskWork} />
        <IndustrialArm side={1} pose={pose} work={deskWork} />
      </group>

      {deskWork ? (
        <SeatedLegs />
      ) : seated ? (
        ([-0.1, 0.1] as const).map((x) => (
          <mesh key={x} position={[x, 0.02, 0.04]} rotation={[0.55, 0, x > 0 ? -0.05 : 0.05]}>
            <boxGeometry args={[0.09, 0.28, 0.09]} />
            <meshStandardMaterial {...armor(0.6, 0.55)} />
          </mesh>
        ))
      ) : (
        <group ref={legs}>
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.12, 0, 0]}>
              <mesh position={[0, -0.12, 0.02]} rotation={[0.12, 0, side * 0.04]}>
                <boxGeometry args={[0.09, 0.32, 0.09]} />
                <meshStandardMaterial {...armor(0.6, 0.55)} />
              </mesh>
              <LedStrip position={[side * 0.05, -0.1, 0]} rotation={[0, 0, Math.PI / 2]} size={[0.14, 0.01, 0.008]} />
              <mesh position={[0, -0.34, 0.06]} rotation={[0.35, 0, 0]}>
                <boxGeometry args={[0.1, 0.06, 0.16]} />
                <meshStandardMaterial color={ARMOR_DARK} roughness={0.55} metalness={0.45} />
              </mesh>
            </group>
          ))}
        </group>
      )}

    </group>
  )
}
