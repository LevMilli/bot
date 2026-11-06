import { useMemo, useRef, type RefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import { CanvasTexture, Matrix4, Quaternion, Vector3, type Group, type MeshStandardMaterial } from 'three'
import type { BotPose } from '../data/botPose'
import { mouseHand, typingHand } from './deskReach'

/**
 * Purple industrial cyberpunk trader — silhouette matched to the user refs:
 * blocky tactical helmet, twin rear blade antennae, exposed hydraulic neck,
 * oversized graffiti pauldrons, circular torso rings, recessed purple LEDs.
 *
 * APEX-CITY format: same desk IK anchors as BotFigure. No per-bot pointLights
 * (black-plaza crash). Plaza cars use `lite`. Markings via cached canvas decals.
 */

const TEX_CACHE = new Map<string, CanvasTexture>()

/** Slightly lifted gunmetal so the figure reads against black chairs/desks. */
const ARMOR = '#18181f'
const ARMOR_DARK = '#0a0a0e'
const ARMOR_EDGE = '#2a2a34'
const METAL = '#3a3a46'
const PURPLE = '#d060ff'
const PURPLE_DIM = '#7a30b8'
const GRAFFITI = '#f4f4f0'

function armor(roughness = 0.58, metalness = 0.65) {
  return {
    color: ARMOR,
    roughness,
    metalness,
    emissive: '#090510',
    emissiveIntensity: 0.1,
  }
}

function neon(intensity = 1.55) {
  return {
    color: PURPLE,
    emissive: PURPLE,
    emissiveIntensity: intensity,
    roughness: 0.22,
    metalness: 0.18,
    toneMapped: false as const,
  }
}

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
      <meshStandardMaterial {...neon(1.65)} />
    </mesh>
  )
}

/** Recessed LED channel — dark trough + glowing strip (matches photo recesses). */
function LedChannel({
  position,
  rotation,
  length = 0.16,
  width = 0.028,
}: {
  position: [number, number, number]
  rotation?: [number, number, number]
  length?: number
  width?: number
}) {
  return (
    <group position={position} rotation={rotation}>
      <mesh>
        <boxGeometry args={[width + 0.01, length + 0.01, 0.016]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.4} roughness={0.7} />
      </mesh>
      <mesh position={[0, 0, 0.006]}>
        <boxGeometry args={[width * 0.55, length * 0.88, 0.01]} />
        <meshStandardMaterial {...neon(1.7)} />
      </mesh>
    </group>
  )
}

function Bolt({ position, r = 0.008 }: { position: [number, number, number]; r?: number }) {
  return (
    <mesh position={position}>
      <cylinderGeometry args={[r, r, 0.01, 8]} />
      <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.28} />
    </mesh>
  )
}

function LedDot({ position, r = 0.012 }: { position: [number, number, number]; r?: number }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[r, 10, 10]} />
      <meshStandardMaterial {...neon(1.9)} />
    </mesh>
  )
}

function Cable({
  position,
  rotation,
  length = 0.08,
  r = 0.007,
}: {
  position: [number, number, number]
  rotation?: [number, number, number]
  length?: number
  r?: number
}) {
  return (
    <mesh position={position} rotation={rotation}>
      <cylinderGeometry args={[r, r, length, 6]} />
      <meshStandardMaterial color="#050508" roughness={0.92} metalness={0.12} />
    </mesh>
  )
}

function Hydraulic({
  position,
  rotation,
  length = 0.09,
}: {
  position: [number, number, number]
  rotation?: [number, number, number]
  length?: number
}) {
  return (
    <group position={position} rotation={rotation}>
      <mesh>
        <cylinderGeometry args={[0.01, 0.01, length, 8]} />
        <meshStandardMaterial color={METAL} metalness={0.92} roughness={0.2} />
      </mesh>
      <mesh position={[0, length * 0.18, 0]}>
        <cylinderGeometry args={[0.017, 0.017, length * 0.32, 8]} />
        <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.32} />
      </mesh>
      {[-0.018, 0, 0.018].map((y) => (
        <mesh key={y} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.015, 0.003, 4, 10]} />
          <meshStandardMaterial color="#50505a" metalness={0.85} roughness={0.28} />
        </mesh>
      ))}
    </group>
  )
}

/** Three-point crown — matches shoulder graffiti icon. */
function CrownMark({ scale = 1 }: { scale?: number }) {
  return (
    <group scale={scale}>
      <mesh position={[0, 0.008, 0]}>
        <boxGeometry args={[0.08, 0.018, 0.01]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.038, 0]}>
        <boxGeometry args={[0.02, 0.045, 0.01]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[-0.032, 0.03, 0]} rotation={[0, 0, 0.4]}>
        <boxGeometry args={[0.018, 0.04, 0.01]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
      <mesh position={[0.032, 0.03, 0]} rotation={[0, 0, -0.4]}>
        <boxGeometry args={[0.018, 0.04, 0.01]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
    </group>
  )
}

function TallyMark() {
  return (
    <group>
      {([-0.032, -0.012, 0.008, 0.028] as const).map((x) => (
        <mesh key={x} position={[x, 0, 0]}>
          <boxGeometry args={[0.009, 0.065, 0.006]} />
          <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0, 0, 0.002]} rotation={[0, 0, -0.72]}>
        <boxGeometry args={[0.009, 0.078, 0.006]} />
        <meshBasicMaterial color={GRAFFITI} toneMapped={false} />
      </mesh>
    </group>
  )
}

function ScratchMarks({ position, rotation }: { position: [number, number, number]; rotation?: [number, number, number] }) {
  return (
    <group position={position} rotation={rotation}>
      <mesh position={[0, 0.02, 0]} rotation={[0, 0, 0.35]}>
        <boxGeometry args={[0.1, 0.003, 0.002]} />
        <meshBasicMaterial color="#3c3c46" toneMapped={false} />
      </mesh>
      <mesh position={[0.015, -0.012, 0]} rotation={[0, 0, -0.2]}>
        <boxGeometry args={[0.07, 0.002, 0.002]} />
        <meshBasicMaterial color="#2a2a32" toneMapped={false} />
      </mesh>
    </group>
  )
}

function graffitiTexture(kind: 'pauldron' | 'unit', mark: string) {
  const key = `${kind}:${mark}`
  const hit = TEX_CACHE.get(key)
  if (hit) return hit

  const c = document.createElement('canvas')
  c.width = kind === 'pauldron' ? 384 : 160
  c.height = kind === 'pauldron' ? 384 : 160
  const ctx = c.getContext('2d')!
  ctx.clearRect(0, 0, c.width, c.height)
  ctx.fillStyle = GRAFFITI
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  if (kind === 'pauldron') {
    // Crown outline
    ctx.lineWidth = 8
    ctx.strokeStyle = GRAFFITI
    ctx.beginPath()
    ctx.moveTo(192, 58)
    ctx.lineTo(148, 118)
    ctx.lineTo(162, 118)
    ctx.lineTo(162, 148)
    ctx.lineTo(222, 148)
    ctx.lineTo(222, 118)
    ctx.lineTo(236, 118)
    ctx.closePath()
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(148, 118)
    ctx.lineTo(118, 72)
    ctx.lineTo(140, 118)
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(236, 118)
    ctx.lineTo(266, 72)
    ctx.lineTo(244, 118)
    ctx.fill()
    // Dripping PIMPS ONLY
    ctx.font = 'bold 58px Impact, Haettenschweiler, Arial Black, sans-serif'
    ctx.fillText('PIMPS', 192, 220)
    ctx.font = 'bold 54px Impact, Haettenschweiler, Arial Black, sans-serif'
    ctx.fillText('ONLY', 192, 280)
    // Drips
    ;[
      [140, 300, 6, 28],
      [175, 298, 5, 36],
      [210, 302, 6, 22],
      [245, 300, 5, 30],
    ].forEach(([x, y, w, h]) => ctx.fillRect(x, y, w, h))
  } else {
    ctx.font = 'bold 96px Impact, Haettenschweiler, Arial Black, sans-serif'
    ctx.fillText(mark.slice(0, 2), 80, 84)
  }

  const tex = new CanvasTexture(c)
  tex.needsUpdate = true
  TEX_CACHE.set(key, tex)
  return tex
}

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
        <boxGeometry args={[0.082, 0.055, 0.065]} />
        <meshStandardMaterial {...armor(0.48, 0.72)} />
      </mesh>
      <mesh position={[0, 0.03, 0.012]}>
        <boxGeometry args={[0.076, 0.02, 0.052]} />
        <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.38} />
      </mesh>
      <LedChannel position={[0, 0, 0.035]} length={0.05} width={0.04} rotation={[Math.PI / 2, 0, 0]} />
      {([-1, 0, 1] as const).map((side) => (
        <group key={side} position={[side * 0.026, 0.042, 0.01]} rotation={[0.14, 0, side * 0.14]}>
          <mesh position={[0, 0.032, 0]}>
            <boxGeometry args={[0.018, 0.055, 0.022]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.42} />
          </mesh>
          <mesh position={[0, 0.062, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.011, 0.003, 4, 10]} />
            <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.28} />
          </mesh>
          <mesh position={[0, 0.092, 0.006]} rotation={[0.28, 0, 0]}>
            <boxGeometry args={[0.015, 0.048, 0.02]} />
            <meshStandardMaterial {...armor(0.5, 0.68)} />
          </mesh>
          <LedDot position={[0, 0.118, 0.014]} r={0.006} />
        </group>
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

/** Chunky photo-matched arm: circular joints, recessed LED channels, tallies. */
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
      position={[side * 0.36, 0.78, 0.02]}
      rotation={[trading ? -2.2 : -0.85, 0, trading ? -side * 0.1 : -side * 0.55]}
    >
      {/* Heavy circular shoulder joint */}
      <mesh>
        <sphereGeometry args={[0.078, 16, 14]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.78} roughness={0.38} emissive={PURPLE_DIM} emissiveIntensity={0.22} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.088, 0.014, 8, 24]} />
        <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.25} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.102, 0.006, 6, 20]} />
        <meshStandardMaterial color={ARMOR_EDGE} metalness={0.82} roughness={0.3} />
      </mesh>
      <LedDot position={[0, 0.025, 0.085]} r={0.011} />
      <LedDot position={[side * 0.055, 0, 0.06]} r={0.008} />

      {/* Upper arm — interlocking plates + recessed LED */}
      <mesh position={[0, 0.175, 0]}>
        <boxGeometry args={[0.125, 0.34, 0.125]} />
        <meshStandardMaterial {...armor(0.52, 0.7)} />
      </mesh>
      <mesh position={[0, 0.175, 0]}>
        <boxGeometry args={[0.1, 0.3, 0.1]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.62} />
      </mesh>
      <mesh position={[side * 0.05, 0.175, 0.03]}>
        <boxGeometry args={[0.045, 0.28, 0.09]} />
        <meshStandardMaterial color={ARMOR_EDGE} metalness={0.74} roughness={0.38} />
      </mesh>
      <LedChannel
        position={[side * 0.068, 0.175, 0]}
        rotation={[0, side * (Math.PI / 2), 0]}
        length={0.24}
        width={0.03}
      />
      <Cable position={[-side * 0.055, 0.17, -0.025]} rotation={[0.12, 0, side * 0.25]} length={0.24} />
      <Hydraulic position={[-side * 0.04, 0.12, -0.03]} rotation={[0.25, 0, 0]} length={0.08} />
      <Bolt position={[side * 0.06, 0.08, 0.05]} />
      <Bolt position={[side * 0.06, 0.16, 0.05]} />
      <Bolt position={[side * 0.06, 0.24, 0.05]} />
      <ScratchMarks position={[side * 0.068, 0.12, 0.02]} rotation={[0, side * (Math.PI / 2), 0]} />
      {/* Upper-arm tallies (ref shows on arm plating) */}
      <group position={[side * 0.068, 0.22, 0.02]} rotation={[0, side * (Math.PI / 2), 0]} scale={0.85}>
        <TallyMark />
      </group>

      {/* Elbow — heavy ring stack */}
      <mesh position={[0, 0.34, 0]}>
        <sphereGeometry args={[0.062, 14, 12]} />
        <meshStandardMaterial color={ARMOR_DARK} metalness={0.82} roughness={0.32} />
      </mesh>
      <mesh position={[0, 0.34, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.07, 0.012, 8, 22]} />
        <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.22} />
      </mesh>
      <mesh position={[0, 0.34, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.082, 0.006, 6, 18]} />
        <meshStandardMaterial {...neon(1.0)} />
      </mesh>
      <LedDot position={[0, 0.34, 0.075]} r={0.01} />

      <group ref={fore} position={[0, 0.34, 0]} rotation={[trading ? -0.05 : -0.5, 0, 0]}>
        <mesh position={[0, 0.155, 0]}>
          <boxGeometry args={[0.11, 0.32, 0.11]} />
          <meshStandardMaterial {...armor(0.5, 0.72)} />
        </mesh>
        <mesh position={[side * 0.045, 0.12, 0.025]}>
          <boxGeometry args={[0.04, 0.13, 0.08]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.74} roughness={0.36} />
        </mesh>
        <mesh position={[side * 0.045, 0.22, 0.025]}>
          <boxGeometry args={[0.038, 0.11, 0.075]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.74} roughness={0.36} />
        </mesh>
        <mesh position={[-side * 0.048, 0.155, 0]}>
          <boxGeometry args={[0.025, 0.26, 0.06]} />
          <meshStandardMaterial color="#040406" metalness={0.4} roughness={0.7} emissive={PURPLE_DIM} emissiveIntensity={0.42} />
        </mesh>
        <LedChannel
          position={[side * 0.06, 0.155, 0]}
          rotation={[0, side * (Math.PI / 2), 0]}
          length={0.22}
          width={0.028}
        />
        <LedChannel position={[0, 0.155, 0.058]} length={0.18} width={0.024} />
        <Cable position={[-side * 0.055, 0.155, 0.02]} length={0.2} r={0.005} />
        <group position={[side * 0.062, 0.14, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
          <TallyMark />
        </group>
        <ScratchMarks position={[side * 0.058, 0.08, 0.03]} rotation={[0, side * (Math.PI / 2), 0]} />
        {/* Neon wrist cuff */}
        <mesh position={[0, 0.32, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.055, 0.011, 8, 18]} />
          <meshStandardMaterial {...neon(1.35)} />
        </mesh>
        <mesh position={[0, 0.3, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.052, 0.007, 6, 16]} />
          <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.26} />
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
          <mesh position={[side * 0.15, 0.22, 0.02]} rotation={[-Math.PI / 2, 0, side * 0.04]}>
            <boxGeometry args={[0.13, 0.32, 0.14]} />
            <meshStandardMaterial {...armor(0.58, 0.58)} />
          </mesh>
          <mesh position={[side * 0.15, 0.22, 0.07]} rotation={[-Math.PI / 2, 0, side * 0.04]}>
            <boxGeometry args={[0.1, 0.24, 0.045]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.4} />
          </mesh>
          <LedChannel position={[side * 0.15, 0.22, 0.1]} length={0.1} width={0.05} rotation={[Math.PI / 2, 0, 0]} />
          <mesh position={[side * 0.15, 0.08, -0.08]} rotation={[0, 0, Math.PI / 2]}>
            <torusGeometry args={[0.05, 0.009, 6, 14]} />
            <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.26} />
          </mesh>
          <LedDot position={[side * 0.15, 0.08, -0.025]} r={0.009} />
          <mesh position={[side * 0.15, -0.05, -0.14]} rotation={[0.15, 0, 0]}>
            <boxGeometry args={[0.115, 0.44, 0.115]} />
            <meshStandardMaterial {...armor(0.6, 0.55)} />
          </mesh>
          <LedChannel
            position={[side * 0.21, -0.05, -0.14]}
            rotation={[0, side * (Math.PI / 2), 0]}
            length={0.22}
            width={0.026}
          />
          <mesh position={[side * 0.15, -0.28, -0.02]} rotation={[0.2, 0, 0]}>
            <boxGeometry args={[0.13, 0.08, 0.22]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.62} roughness={0.52} />
          </mesh>
          <LedStrip position={[side * 0.15, -0.25, 0.09]} size={[0.09, 0.012, 0.009]} />
        </group>
      ))}
    </>
  )
}

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
  unitMark?: string
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
      stripPulse.current.emissiveIntensity = 1.4 + Math.sin(t * 2.6) * 0.4
    }
  })

  // Plaza car LOD — black+purple silhouette only.
  if (lite) {
    return (
      <group ref={body} position={anchor}>
        <mesh position={[0, 0.55, 0]}>
          <boxGeometry args={[0.4, 0.52, 0.28]} />
          <meshStandardMaterial {...armor(0.55, 0.65)} />
        </mesh>
        <mesh position={[0, 0.55, 0.15]}>
          <boxGeometry args={[0.22, 0.02, 0.01]} />
          <meshStandardMaterial {...neon(1.3)} />
        </mesh>
        <group ref={head} position={[0, 1.0, 0.02]}>
          <mesh position={[0, 0.14, 0]}>
            <boxGeometry args={[0.3, 0.28, 0.32]} />
            <meshStandardMaterial {...armor(0.5, 0.7)} />
          </mesh>
          <LedDot position={[-0.055, 0.14, 0.17]} r={0.018} />
          <LedDot position={[0.055, 0.14, 0.17]} r={0.018} />
          <mesh position={[-0.075, 0.38, -0.08]} rotation={[0.35, 0, -0.18]}>
            <boxGeometry args={[0.022, 0.32, 0.04]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.34} />
          </mesh>
          <mesh position={[0.075, 0.38, -0.08]} rotation={[0.35, 0, 0.18]}>
            <boxGeometry args={[0.022, 0.32, 0.04]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.34} />
          </mesh>
        </group>
        {([-1, 1] as const).map((side) => (
          <mesh key={side} position={[side * 0.3, 0.72, 0]} rotation={[0.15, 0, side * 0.45]}>
            <boxGeometry args={[0.14, 0.42, 0.12]} />
            <meshStandardMaterial {...armor(0.55, 0.6)} />
          </mesh>
        ))}
        {seated || deskWork ? <SeatedLegs /> : null}
      </group>
    )
  }

  // Suite interiors are scaled ~0.62 — nudge desk bots up so armor/antennae still read.
  const suiteBoost = deskWork ? 1.14 : 1

  return (
    <group ref={body} position={anchor} scale={suiteBoost}>
      <group ref={torso}>
        {/* Pelvis */}
        <mesh position={[0, deskWork ? 0.3 : 0.14, deskWork ? 0.04 : 0]}>
          <boxGeometry args={[0.32, 0.18, 0.26]} />
          <meshStandardMaterial {...armor(0.58, 0.6)} />
        </mesh>
        <mesh position={[0, deskWork ? 0.36 : 0.2, deskWork ? 0.04 : 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.15, 0.014, 6, 22]} />
          <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.26} />
        </mesh>

        {/* Thick torso cage — photo: wide powerful frame */}
        <mesh position={[0, 0.56, 0.02]}>
          <boxGeometry args={[0.48, 0.56, 0.34]} />
          <meshStandardMaterial {...armor(0.52, 0.68)} />
        </mesh>
        <mesh position={[0, 0.56, 0]}>
          <boxGeometry args={[0.36, 0.48, 0.24]} />
          <meshStandardMaterial color={ARMOR_DARK} metalness={0.45} roughness={0.68} emissive={PURPLE_DIM} emissiveIntensity={0.32} />
        </mesh>
        {/* Front plate stack */}
        <mesh position={[0, 0.7, 0.16]}>
          <boxGeometry args={[0.36, 0.18, 0.06]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.36} />
        </mesh>
        <mesh position={[0, 0.52, 0.17]}>
          <boxGeometry args={[0.3, 0.16, 0.05]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.75} roughness={0.36} />
        </mesh>
        <mesh position={[0, 0.38, 0.15]}>
          <boxGeometry args={[0.24, 0.1, 0.045]} />
          <meshStandardMaterial {...armor(0.5, 0.7)} />
        </mesh>

        {/* Circular structural rings (ref: shoulder/chest rings) */}
        <mesh position={[0, 0.72, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.22, 0.02, 8, 28]} />
          <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.24} />
        </mesh>
        <mesh position={[0, 0.72, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.255, 0.009, 6, 24]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.82} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.5, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.2, 0.012, 6, 24]} />
          <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.28} />
        </mesh>
        <LedDot position={[0.22, 0.72, 0]} r={0.009} />
        <LedDot position={[-0.22, 0.72, 0]} r={0.009} />

        {/* Mechanical spine (OTS hero detail) */}
        <mesh position={[0, 0.56, -0.14]}>
          <boxGeometry args={[0.07, 0.52, 0.06]} />
          <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.32} />
        </mesh>
        {[0.36, 0.44, 0.52, 0.6, 0.68, 0.76].map((y) => (
          <mesh key={y} position={[0, y, -0.16]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.052, 0.009, 6, 16]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.3} />
          </mesh>
        ))}
        <LedChannel position={[0, 0.56, -0.18]} length={0.42} width={0.035} rotation={[Math.PI / 2, 0, 0]} />
        <Cable position={[-0.055, 0.56, -0.17]} rotation={[0.04, 0, 0.12]} length={0.4} />
        <Cable position={[0.055, 0.56, -0.17]} rotation={[0.04, 0, -0.12]} length={0.4} />

        {/* Side armor + underglow gaps */}
        {([-1, 1] as const).map((side) => (
          <group key={side}>
            <mesh position={[side * 0.26, 0.56, 0.02]}>
              <boxGeometry args={[0.07, 0.46, 0.3]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.38} />
            </mesh>
            <mesh position={[side * 0.3, 0.56, 0.02]}>
              <boxGeometry args={[0.022, 0.4, 0.22]} />
              <meshStandardMaterial color={ARMOR_DARK} metalness={0.4} roughness={0.65} emissive={PURPLE_DIM} emissiveIntensity={0.28} />
            </mesh>
            <LedChannel
              position={[side * 0.305, 0.62, 0.08]}
              rotation={[0, side * (Math.PI / 2), 0]}
              length={0.14}
              width={0.028}
            />
            <ScratchMarks position={[side * 0.305, 0.48, 0.1]} rotation={[0, side * (Math.PI / 2), 0]} />
            <Bolt position={[side * 0.295, 0.72, 0.12]} />
            <Bolt position={[side * 0.295, 0.56, 0.12]} />
            <Bolt position={[side * 0.295, 0.4, 0.12]} />
          </group>
        ))}

        {/* Chest LED lattice */}
        <LedChannel position={[-0.14, 0.68, 0.195]} length={0.1} width={0.05} rotation={[Math.PI / 2, 0, 0]} />
        <LedChannel position={[0.14, 0.68, 0.195]} length={0.1} width={0.05} rotation={[Math.PI / 2, 0, 0]} />
        <mesh position={[0, 0.48, 0.195]}>
          <boxGeometry args={[0.24, 0.016, 0.012]} />
          <meshStandardMaterial ref={stripPulse} {...neon(1.5)} />
        </mesh>
        <LedDot position={[0, 0.62, 0.195]} r={0.011} />

        {/* Oversized graffiti pauldrons — photo hero surface */}
        {([-1, 1] as const).map((side) => (
          <group key={side} position={[side * 0.42, 0.92, 0.05]}>
            {/* Flat angular pauldron plate */}
            <mesh rotation={[0.1, side * 0.18, side * 0.5]}>
              <boxGeometry args={[0.36, 0.2, 0.42]} />
              <meshStandardMaterial {...armor(0.45, 0.75)} />
            </mesh>
            <mesh position={[0, 0.08, 0]} rotation={[0.1, side * 0.18, side * 0.48]}>
              <boxGeometry args={[0.34, 0.04, 0.4]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.32} />
            </mesh>
            <mesh position={[0, -0.02, 0.05]} rotation={[0.1, side * 0.18, side * 0.48]}>
              <boxGeometry args={[0.24, 0.07, 0.24]} />
              <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.55} emissive={PURPLE_DIM} emissiveIntensity={0.2} />
            </mesh>
            <LedChannel position={[side * 0.02, 0.02, 0.16]} length={0.18} width={0.04} rotation={[Math.PI / 2, 0, 0]} />
            <LedChannel position={[side * 0.02, -0.04, 0.16]} length={0.12} width={0.032} rotation={[Math.PI / 2, 0, 0]} />
            <Bolt position={[side * 0.1, 0.07, 0.14]} />
            <Bolt position={[side * 0.1, -0.02, 0.14]} />
            <Bolt position={[side * 0.1, 0.07, -0.06]} />
            <Bolt position={[side * 0.1, -0.02, -0.06]} />
            <ScratchMarks position={[side * 0.14, 0.02, 0.1]} rotation={[0, side * (Math.PI / 2), 0]} />
            {/* Crown + PIMPS ONLY facing outward */}
            <mesh position={[side * 0.165, 0.02, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <planeGeometry args={[0.26, 0.26]} />
              <meshBasicMaterial map={maps!.pauldron} transparent toneMapped={false} depthWrite={false} />
            </mesh>
            <group position={[side * 0.168, 0.09, 0.02]} rotation={[0, side * (Math.PI / 2), 0]}>
              <CrownMark scale={1.15} />
            </group>
          </group>
        ))}

        {/* Collar */}
        <mesh position={[0, 0.92, 0.06]}>
          <boxGeometry args={[0.3, 0.055, 0.18]} />
          <meshStandardMaterial color={ARMOR_EDGE} metalness={0.78} roughness={0.34} />
        </mesh>
        <LedDot position={[-0.1, 0.94, 0.12]} r={0.01} />
        <LedDot position={[0.1, 0.94, 0.12]} r={0.01} />
        <LedDot position={[0, 0.95, 0.14]} r={0.008} />

        {/* ── Tactical helmet (photo: blocky + twin rear blades) ── */}
        <group ref={head} position={[0, 1.04, 0.02]}>
          {/* Exposed hydraulic neck */}
          <mesh position={[0, -0.07, 0]}>
            <cylinderGeometry args={[0.055, 0.065, 0.12, 12]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.72} roughness={0.4} emissive={PURPLE_DIM} emissiveIntensity={0.55} />
          </mesh>
          <mesh position={[0, -0.07, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.062, 0.01, 6, 16]} />
            <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.24} />
          </mesh>
          <Hydraulic position={[-0.038, -0.055, 0.025]} length={0.1} />
          <Hydraulic position={[0.038, -0.055, 0.025]} length={0.1} />
          <Hydraulic position={[0, -0.055, -0.04]} rotation={[0.2, 0, 0]} length={0.095} />
          <mesh position={[0, -0.055, -0.045]}>
            <cylinderGeometry args={[0.015, 0.015, 0.09, 6]} />
            <meshStandardMaterial color="#1a1020" metalness={0.4} roughness={0.55} emissive={PURPLE} emissiveIntensity={0.6} />
          </mesh>
          <Cable position={[-0.05, -0.045, -0.02]} rotation={[0.3, 0, 0.4]} length={0.09} />
          <Cable position={[0.05, -0.045, -0.02]} rotation={[0.3, 0, -0.4]} length={0.09} />
          <Cable position={[-0.025, -0.045, 0.045]} rotation={[0.15, 0.25, 0]} length={0.08} r={0.005} />
          <Cable position={[0.025, -0.045, 0.045]} rotation={[0.15, -0.25, 0]} length={0.08} r={0.005} />

          {/* Helmet shell */}
          <mesh position={[0, 0.16, 0.02]}>
            <boxGeometry args={[0.4, 0.32, 0.42]} />
            <meshStandardMaterial {...armor(0.45, 0.74)} />
          </mesh>
          <mesh position={[0, 0.16, 0.02]}>
            <boxGeometry args={[0.014, 0.3, 0.43]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.55} />
          </mesh>
          <mesh position={[0, 0.16, 0.02]}>
            <boxGeometry args={[0.41, 0.012, 0.43]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.5} roughness={0.55} />
          </mesh>
          {/* Cheek plates */}
          {([-1, 1] as const).map((side) => (
            <mesh key={side} position={[side * 0.205, 0.1, 0.04]}>
              <boxGeometry args={[0.055, 0.2, 0.3]} />
              <meshStandardMaterial color={ARMOR_EDGE} metalness={0.72} roughness={0.38} />
            </mesh>
          ))}
          {/* Crown plate */}
          <mesh position={[0, 0.33, 0.02]}>
            <boxGeometry args={[0.36, 0.08, 0.38]} />
            <meshStandardMaterial color={ARMOR_EDGE} metalness={0.74} roughness={0.36} />
          </mesh>
          <Bolt position={[-0.13, 0.36, 0.14]} />
          <Bolt position={[0.13, 0.36, 0.14]} />
          <Bolt position={[-0.13, 0.36, -0.1]} />
          <Bolt position={[0.13, 0.36, -0.1]} />
          <Bolt position={[0, 0.36, 0.18]} />
          {/* Brow + visor */}
          <mesh position={[0, 0.23, 0.21]}>
            <boxGeometry args={[0.32, 0.045, 0.055]} />
            <meshStandardMaterial color={METAL} metalness={0.85} roughness={0.28} />
          </mesh>
          <mesh position={[0, 0.13, 0.2]} rotation={[-0.42, 0, 0]}>
            <boxGeometry args={[0.36, 0.18, 0.075]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.68} roughness={0.34} />
          </mesh>
          <ScratchMarks position={[0.1, 0.18, 0.22]} />

          {/* Face sensor bay — horizontal slit + small purple points (photo: not giant orbs) */}
          <mesh position={[0, 0.145, 0.235]}>
            <boxGeometry args={[0.26, 0.048, 0.022]} />
            <meshStandardMaterial color="#030306" metalness={0.45} roughness={0.55} />
          </mesh>
          <mesh position={[0, 0.145, 0.246]}>
            <boxGeometry args={[0.22, 0.022, 0.01]} />
            <meshStandardMaterial {...neon(1.35)} />
          </mesh>
          {([-0.08, -0.04, 0.04, 0.08] as const).map((x) => (
            <LedDot key={x} position={[x, 0.145, 0.255]} r={0.009} />
          ))}
          <LedDot position={[0, 0.1, 0.252]} r={0.01} />

          {/* Side four-dot sensor arrays */}
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.21, 0.145, 0.02]}>
              <mesh>
                <boxGeometry args={[0.028, 0.075, 0.17]} />
                <meshStandardMaterial color="#030306" metalness={0.5} roughness={0.5} />
              </mesh>
              {([-0.055, -0.018, 0.018, 0.055] as const).map((z) => (
                <LedDot key={z} position={[side * 0.016, 0, z]} r={0.013} />
              ))}
            </group>
          ))}

          {/* Jaw underglow */}
          <LedChannel position={[0, 0.015, 0.16]} length={0.16} width={0.05} rotation={[Math.PI / 2, 0, 0]} />
          <mesh position={[0, 0.015, 0.13]}>
            <boxGeometry args={[0.22, 0.05, 0.1]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.7} roughness={0.4} emissive={PURPLE_DIM} emissiveIntensity={0.4} />
          </mesh>
          <Hydraulic position={[-0.065, -0.005, 0.09]} rotation={[1.15, 0, 0]} length={0.055} />
          <Hydraulic position={[0.065, -0.005, 0.09]} rotation={[1.15, 0, 0]} length={0.055} />

          {/* Twin long rear blade antennae — photo signature (tall enough to read at suite scale) */}
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.1, 0.32, -0.16]} rotation={[0.55, 0, side * 0.22]}>
              <mesh position={[0, 0.28, 0]}>
                <boxGeometry args={[0.036, 0.58, 0.068]} />
                <meshStandardMaterial color={ARMOR_EDGE} metalness={0.8} roughness={0.3} />
              </mesh>
              {[0.08, 0.18, 0.28, 0.38, 0.48].map((y) => (
                <mesh key={y} position={[0, y, 0.014]}>
                  <boxGeometry args={[0.04, 0.055, 0.03]} />
                  <meshStandardMaterial color={ARMOR_DARK} />
                </mesh>
              ))}
              <mesh position={[0, 0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[0.04, 0.04, 0.028, 10]} />
                <meshStandardMaterial color={METAL} metalness={0.9} roughness={0.24} />
              </mesh>
              <Bolt position={[0, 0.02, 0.035]} />
              <LedDot position={[0, 0.58, 0]} r={0.014} />
              <LedChannel position={[0, 0.28, 0.036]} length={0.36} width={0.02} />
            </group>
          ))}

          {/* Unit "22" — cheeks + rear skull */}
          <mesh position={[0.215, 0.05, 0.1]} rotation={[0, Math.PI / 2, 0]}>
            <planeGeometry args={[0.12, 0.12]} />
            <meshBasicMaterial map={maps!.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <mesh position={[-0.215, 0.05, 0.1]} rotation={[0, -Math.PI / 2, 0]}>
            <planeGeometry args={[0.12, 0.12]} />
            <meshBasicMaterial map={maps!.unit} transparent toneMapped={false} depthWrite={false} />
          </mesh>
          <mesh position={[0, 0.15, -0.2]}>
            <boxGeometry args={[0.18, 0.18, 0.025]} />
            <meshStandardMaterial color={ARMOR_DARK} metalness={0.6} roughness={0.45} />
          </mesh>
          <mesh position={[0, 0.15, -0.215]} rotation={[0, Math.PI, 0]}>
            <planeGeometry args={[0.15, 0.15]} />
            <meshBasicMaterial map={maps!.unit} transparent opacity={0.55} toneMapped={false} depthWrite={false} />
          </mesh>
          <Bolt position={[-0.15, 0.28, 0.14]} />
          <Bolt position={[0.15, 0.28, 0.14]} />
          <Bolt position={[-0.15, 0.28, -0.1]} />
          <Bolt position={[0.15, 0.28, -0.1]} />
          <Bolt position={[-0.15, 0.08, 0.16]} />
          <Bolt position={[0.15, 0.08, 0.16]} />
        </group>

        <IndustrialArm side={-1} pose={pose} work={deskWork} />
        <IndustrialArm side={1} pose={pose} work={deskWork} />
      </group>

      {deskWork ? (
        <SeatedLegs />
      ) : seated ? (
        ([-0.12, 0.12] as const).map((x) => (
          <mesh key={x} position={[x, 0.02, 0.04]} rotation={[0.55, 0, x > 0 ? -0.05 : 0.05]}>
            <boxGeometry args={[0.1, 0.3, 0.1]} />
            <meshStandardMaterial {...armor(0.58, 0.55)} />
          </mesh>
        ))
      ) : (
        <group ref={legs}>
          {([-1, 1] as const).map((side) => (
            <group key={side} position={[side * 0.13, 0, 0]}>
              <mesh position={[0, -0.12, 0.02]} rotation={[0.12, 0, side * 0.04]}>
                <boxGeometry args={[0.11, 0.36, 0.11]} />
                <meshStandardMaterial {...armor(0.58, 0.55)} />
              </mesh>
              <LedChannel
                position={[side * 0.06, -0.1, 0]}
                rotation={[0, side * (Math.PI / 2), 0]}
                length={0.18}
                width={0.024}
              />
              <mesh position={[0, -0.3, 0.04]} rotation={[0, 0, Math.PI / 2]}>
                <torusGeometry args={[0.045, 0.008, 6, 12]} />
                <meshStandardMaterial color={METAL} metalness={0.88} roughness={0.26} />
              </mesh>
              <mesh position={[0, -0.36, 0.07]} rotation={[0.35, 0, 0]}>
                <boxGeometry args={[0.12, 0.07, 0.2]} />
                <meshStandardMaterial color={ARMOR_DARK} roughness={0.55} metalness={0.48} />
              </mesh>
              <LedStrip position={[0, -0.34, 0.14]} size={[0.08, 0.012, 0.009]} />
            </group>
          ))}
        </group>
      )}
    </group>
  )
}
