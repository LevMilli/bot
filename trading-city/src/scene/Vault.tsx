import { useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { CanvasTexture, SRGBColorSpace, type Group, type Mesh } from 'three'
import type { BotRow, Desk } from '../types'
import { VaultHologram } from '../hud/Holograms'

const SHELL = '#07060e'
const BRASS = '#c9a227'
const GOLD = '#f9c80e'
const CYAN = '#2de2e6'
const WINDOW = '#f4f0d4'

/** Engraved combination face. Numbers stay dark so they read without neon bloom. */
function useDialFace() {
  return useMemo(() => {
    const size = 512
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const g = canvas.getContext('2d')
    if (!g) return null
    const c = size / 2
    g.fillStyle = '#c6a15a'
    g.beginPath()
    g.arc(c, c, c - 2, 0, Math.PI * 2)
    g.fill()
    g.fillStyle = '#5c4318'
    g.beginPath()
    g.arc(c, c, 86, 0, Math.PI * 2)
    g.fill()
    g.strokeStyle = '#1a1408'
    g.fillStyle = '#1a1408'
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.font = '700 34px sans-serif'
    const ticks = 40
    for (let i = 0; i < ticks; i++) {
      const a = -Math.PI / 2 + (i / ticks) * Math.PI * 2
      const major = i % 5 === 0
      const outer = c - 22
      const inner = major ? c - 72 : c - 46
      g.lineWidth = major ? 5 : 2
      g.beginPath()
      g.moveTo(c + Math.cos(a) * inner, c + Math.sin(a) * inner)
      g.lineTo(c + Math.cos(a) * outer, c + Math.sin(a) * outer)
      g.stroke()
      if (major) {
        const tr = c - 104
        g.fillText(String((i / 5) * 10), c + Math.cos(a) * tr, c + Math.sin(a) * tr)
      }
    }
    const tex = new CanvasTexture(canvas)
    tex.colorSpace = SRGBColorSpace
    tex.anisotropy = 8
    tex.needsUpdate = true
    return tex
  }, [])
}

function VaultDoor({ clickProps = {} }: { clickProps?: Record<string, unknown> }) {
  const dial = useRef<Group>(null)
  const face = useDialFace()
  useFrame(({ clock }) => {
    if (dial.current) dial.current.rotation.z = clock.getElapsedTime() * 0.15
  })
  const bolts = Array.from({ length: 16 }, (_, i) => {
    const a = (i / 16) * Math.PI * 2
    return [Math.cos(a) * 0.84, Math.sin(a) * 0.84] as const
  })
  return (
    <group position={[0, 1.35, 2.38]}>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -0.04]} {...clickProps}>
        <cylinderGeometry args={[1.14, 1.14, 0.2, 48]} />
        <meshStandardMaterial color="#2a2e36" metalness={0.78} roughness={0.32} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, 0.02]}>
        <cylinderGeometry args={[0.9, 0.9, 0.08, 48]} />
        <meshStandardMaterial color="#1a1d24" metalness={0.7} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, 0.07]}>
        <torusGeometry args={[1.02, 0.07, 12, 48]} />
        <meshStandardMaterial color={BRASS} metalness={0.82} roughness={0.28} />
      </mesh>
      <mesh position={[0, 0, 0.06]}>
        <torusGeometry args={[0.64, 0.022, 10, 40]} />
        <meshStandardMaterial color={BRASS} metalness={0.75} roughness={0.32} />
      </mesh>
      {bolts.map(([x, y], i) => (
        <mesh key={i} position={[x, y, 0.1]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.038, 0.038, 0.03, 12]} />
          <meshStandardMaterial color="#8d7a45" metalness={0.8} roughness={0.3} />
        </mesh>
      ))}
      <group ref={dial} position={[0, 0, 0.1]}>
        <mesh>
          <circleGeometry args={[0.5, 48]} />
          <meshStandardMaterial map={face ?? undefined} color={face ? '#ffffff' : BRASS} metalness={0.25} roughness={0.55} />
        </mesh>
        <mesh>
          <torusGeometry args={[0.5, 0.028, 10, 40]} />
          <meshStandardMaterial color="#6e5420" metalness={0.7} roughness={0.32} />
        </mesh>
        <mesh position={[0, 0, 0.03]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.09, 0.09, 0.05, 20]} />
          <meshStandardMaterial color={BRASS} metalness={0.84} roughness={0.24} />
        </mesh>
        <mesh position={[0.18, 0, 0.045]}>
          <boxGeometry args={[0.3, 0.08, 0.05]} />
          <meshStandardMaterial color={BRASS} metalness={0.84} roughness={0.24} />
        </mesh>
        <mesh position={[0.34, 0, 0.05]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.075, 0.07, 0.06, 16]} />
          <meshStandardMaterial color="#e0c36a" metalness={0.7} roughness={0.28} />
        </mesh>
      </group>
      <mesh position={[0, 0.6, 0.12]}>
        <boxGeometry args={[0.028, 0.1, 0.02]} />
        <meshStandardMaterial color="#f2e2a8" metalness={0.4} roughness={0.35} />
      </mesh>
    </group>
  )
}

/** Plaza strongbox. Same dark shell and neon as the towers, with a round lock facing the approach. */
export function Vault({
  lights = true,
  position = [0, 0, 5.2],
  desk,
  bots = [],
  workers = 0,
  showHolo = true,
  onOpen,
}: {
  lights?: boolean
  /** Plaza keeps the vault toward the overview camera. The office window places it down the street. */
  position?: [number, number, number]
  desk?: Desk
  bots?: BotRow[]
  workers?: number
  showHolo?: boolean
  /** Enter the bank lobby when the vault is clicked. */
  onOpen?: () => void
}) {
  const beacon = useRef<Mesh>(null)
  // The card is an HTML overlay. Mounted on the very first render it can attach
  // before the canvas sits in the page and never show until you leave and come
  // back. Wait for the first drawn frame, then mount it.
  const [holoReady, setHoloReady] = useState(false)

  useFrame(({ clock }) => {
    if (!holoReady) setHoloReady(true)
    if (!beacon.current) return
    const mat = beacon.current.material as { opacity?: number }
    if (mat.opacity != null) mat.opacity = 0.55 + Math.sin(clock.getElapsedTime() * 1.8) * 0.25
  })

  const clickProps = onOpen
    ? {
        onClick: (e: { stopPropagation: () => void }) => {
          e.stopPropagation()
          onOpen()
        },
        onPointerOver: () => {
          document.body.style.cursor = 'pointer'
        },
        onPointerOut: () => {
          document.body.style.cursor = 'default'
        },
      }
    : {}

  const slots: [number, number, number, number][] = []
  for (let row = 0; row < 2; row++) {
    const y = 1.05 + row * 0.72
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2
      const wrapped = Math.atan2(Math.sin(a), Math.cos(a))
      if (Math.abs(wrapped) < 0.95 && Math.cos(a) > 0) continue
      slots.push([Math.sin(a) * 2.2, y, Math.cos(a) * 2.2, -a])
    }
  }

  return (
    <group position={position}>
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]} {...clickProps}>
        <circleGeometry args={[3.35, 32]} />
        <meshBasicMaterial color="#050510" />
      </mesh>
      <mesh position={[0, 0.035, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[3.15, 3.42, 40]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[2.72, 2.86, 40]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.7} toneMapped={false} />
      </mesh>

      <mesh position={[0, 0.22, 0]} {...clickProps}>
        <cylinderGeometry args={[2.55, 2.7, 0.36, 8]} />
        <meshStandardMaterial color="#0c0c14" metalness={0.35} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.42, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.55, 0.03, 8, 32]} />
        <meshStandardMaterial color={BRASS} metalness={0.7} roughness={0.35} />
      </mesh>

      <mesh position={[0, 1.55, 0]} {...clickProps}>
        <cylinderGeometry args={[2.12, 2.12, 2.15, 8]} />
        <meshStandardMaterial color={SHELL} metalness={0.2} roughness={0.78} />
      </mesh>

      {slots.map(([x, y, z, rot], i) => (
        <mesh key={i} position={[x, y, z]} rotation={[0, rot, 0]}>
          <boxGeometry args={[0.22, 0.12, 0.06]} />
          <meshBasicMaterial color={WINDOW} toneMapped={false} />
        </mesh>
      ))}

      <mesh position={[0, 2.68, 0]}>
        <cylinderGeometry args={[2.16, 2.12, 0.16, 8]} />
        <meshStandardMaterial color="#0c0c14" emissive={GOLD} emissiveIntensity={0.45} />
      </mesh>
      {/* Lock read from the overview camera: a wheel on the roof, same idea as the door. */}
      <mesh position={[0, 2.8, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.62, 0.78, 24]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0, 2.82, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.28, 0.36, 20]} />
        <meshBasicMaterial color={CYAN} toneMapped={false} />
      </mesh>
      <mesh position={[0, 2.83, 0]}>
        <boxGeometry args={[1.35, 0.04, 0.07]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>
      <mesh position={[0, 2.83, 0]}>
        <boxGeometry args={[0.07, 0.04, 1.35]} />
        <meshBasicMaterial color={GOLD} toneMapped={false} />
      </mesh>

      <mesh ref={beacon} position={[0, 2.98, 0]}>
        <cylinderGeometry args={[0.07, 0.11, 0.42, 8]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.7} depthWrite={false} toneMapped={false} />
      </mesh>

      <VaultDoor clickProps={clickProps} />

      <mesh position={[0, 0.14, 2.85]} {...clickProps}>
        <boxGeometry args={[1.7, 0.2, 0.7]} />
        <meshStandardMaterial color="#101018" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.25, 3.12]}>
        <boxGeometry args={[1.55, 0.02, 0.05]} />
        <meshStandardMaterial color={BRASS} metalness={0.7} roughness={0.35} />
      </mesh>

      {[Math.PI / 4, (3 * Math.PI) / 4, (5 * Math.PI) / 4, (7 * Math.PI) / 4].map((a) => (
        <group key={a} position={[Math.cos(a) * 3.05, 0, Math.sin(a) * 3.05]}>
          <mesh position={[0, 0.38, 0]}>
            <boxGeometry args={[0.1, 0.7, 0.1]} />
            <meshBasicMaterial color="#12121c" />
          </mesh>
          <mesh position={[0, 0.76, 0]}>
            <boxGeometry args={[0.16, 0.08, 0.16]} />
            <meshBasicMaterial color={CYAN} toneMapped={false} />
          </mesh>
        </group>
      ))}

      {lights && <pointLight position={[0, 3.4, 1.2]} intensity={1.15} color="#9ee7ff" distance={14} />}

      {showHolo && holoReady && <VaultHologram desk={desk} bots={bots} workers={workers} />}
    </group>
  )
}
