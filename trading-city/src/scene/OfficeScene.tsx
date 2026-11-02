import { useEffect, useMemo, useRef } from 'react'
import { OrbitControls, PerspectiveCamera } from '@react-three/drei'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
import { DoubleSide, type Group, type Texture } from 'three'
import type { BotRow, Desk } from '../types'
import { useFrame } from '@react-three/fiber'
import {
  centerMonitorTexture,
  leftMonitorTexture,
  rightMonitorTexture,
} from '../hud/monitorTextures'
import { botPose } from '../data/botPose'
import { NeonBloom } from './Effects'
import { BotFigure } from './BotFigure'
import { StreetCity } from './WindowCity'
import { KEY_TOP, MOUSE_TOP, mouseHand } from './deskReach'
import { WallStockChart } from './WallCharts'

type Props = {
  bot: BotRow
  bots?: BotRow[]
  desk?: Desk
  onOpenScreens?: () => void
}

const FRAME = '#3a2a68'
const WALL = '#241848'
const TRIM = '#7ec8d8'

function MonitorFrame({
  position,
  rotation,
  size,
  edge,
  map,
  onOpen,
}: {
  position: [number, number, number]
  rotation: [number, number, number]
  size: [number, number]
  edge: string
  map: Texture
  onOpen?: () => void
}) {
  const [w, h] = size
  return (
    <group
      position={position}
      rotation={rotation}
      onClick={(e) => {
        e.stopPropagation()
        onOpen?.()
      }}
      onPointerOver={() => {
        document.body.style.cursor = 'pointer'
      }}
      onPointerOut={() => {
        document.body.style.cursor = 'default'
      }}
    >
      <mesh>
        <boxGeometry args={[w, h, 0.05]} />
        <meshStandardMaterial color="#0c1018" metalness={0.35} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0, 0.028]}>
        <planeGeometry args={[w * 0.9, h * 0.84]} />
        <meshBasicMaterial map={map} toneMapped={false} />
      </mesh>
      <mesh position={[0, h / 2 + 0.012, 0.02]}>
        <boxGeometry args={[w + 0.03, 0.022, 0.03]} />
        <meshBasicMaterial color={edge} toneMapped={false} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.012, 0.02]}>
        <boxGeometry args={[w + 0.03, 0.022, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[-w / 2 - 0.012, 0, 0.02]}>
        <boxGeometry args={[0.022, h + 0.02, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      <mesh position={[w / 2 + 0.012, 0, 0.02]}>
        <boxGeometry args={[0.022, h + 0.02, 0.03]} />
        <meshStandardMaterial color="#141820" metalness={0.4} roughness={0.45} />
      </mesh>
      {/* stand */}
      <mesh position={[0, -h / 2 - 0.16, 0.04]}>
        <boxGeometry args={[0.06, 0.26, 0.06]} />
        <meshStandardMaterial color="#1c222e" metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, -h / 2 - 0.28, 0.06]}>
        <boxGeometry args={[0.28, 0.02, 0.16]} />
        <meshStandardMaterial color="#1c222e" metalness={0.55} roughness={0.35} />
      </mesh>
    </group>
  )
}

function Ceiling() {
  const tiles: [number, number][] = []
  for (let x = -2; x <= 2; x++) {
    for (let z = -1; z <= 2; z++) {
      tiles.push([x * 1.55, z * 1.35 - 0.4])
    }
  }
  return (
    <group>
      <mesh position={[0, 3.38, 0.7]} rotation={[Math.PI / 2, 0, 0]}>
        <planeGeometry args={[16, 8.2]} />
        <meshStandardMaterial color="#1a1230" roughness={0.92} side={DoubleSide} />
      </mesh>
      {tiles.map(([x, z]) => (
        <mesh key={`${x}-${z}`} position={[x, 3.36, z]} rotation={[Math.PI / 2, 0, 0]}>
          <planeGeometry args={[1.42, 1.18]} />
          <meshStandardMaterial color="#261848" roughness={0.85} metalness={0.04} side={DoubleSide} />
        </mesh>
      ))}
      {/* troffer lights */}
      {([-1.15, 1.15] as const).map((x) => (
        <mesh key={x} position={[x, 3.34, 0.35]}>
          <boxGeometry args={[0.28, 0.04, 2.6]} />
          <meshBasicMaterial color="#e7f6ff" toneMapped={false} />
        </mesh>
      ))}
    </group>
  )
}

function SideWall({ x, rot }: { x: number; rot: number }) {
  return (
    <group position={[x, 1.69, 0.7]} rotation={[0, rot, 0]}>
      <mesh>
        <planeGeometry args={[8.2, 3.38]} />
        <meshStandardMaterial color={WALL} roughness={0.9} side={DoubleSide} />
      </mesh>
      <mesh position={[0, -0.85, 0.01]}>
        <planeGeometry args={[8.2, 1.35]} />
        <meshStandardMaterial color="#1b212e" roughness={0.82} side={DoubleSide} />
      </mesh>
      <mesh position={[0, -0.16, 0.02]}>
        <boxGeometry args={[8.2, 0.04, 0.02]} />
        <meshStandardMaterial color={TRIM} metalness={0.35} roughness={0.45} />
      </mesh>
      <mesh position={[0, -1.66, 0.02]}>
        <boxGeometry args={[8.2, 0.06, 0.03]} />
        <meshStandardMaterial color="#0d1118" metalness={0.4} roughness={0.4} />
      </mesh>
    </group>
  )
}

function Door() {
  return (
    <group position={[-7.85, 1.15, 1.35]} rotation={[0, Math.PI / 2, 0]}>
      <mesh position={[0, 0, 0.02]}>
        <boxGeometry args={[1.05, 2.25, 0.06]} />
        <meshStandardMaterial color="#0e121a" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0, 0.06]}>
        <boxGeometry args={[0.92, 2.12, 0.02]} />
        <meshStandardMaterial color="#171c28" roughness={0.6} />
      </mesh>
      <mesh position={[0.32, 0, 0.09]}>
        <boxGeometry args={[0.04, 0.16, 0.04]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
      </mesh>
    </group>
  )
}

function Credenza() {
  return (
    <group position={[3.15, 0.42, -1.15]}>
      <mesh>
        <boxGeometry args={[0.55, 0.78, 1.7]} />
        <meshStandardMaterial color="#161b26" metalness={0.25} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.08, 0.28]}>
        <boxGeometry args={[0.52, 0.02, 0.7]} />
        <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, -0.22, 0.28]}>
        <boxGeometry args={[0.52, 0.02, 0.7]} />
        <meshStandardMaterial color="#2a3344" metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[-0.28, 0.55, 0]}>
        <boxGeometry args={[0.02, 0.28, 0.02]} />
        <meshStandardMaterial color="#9aa3b5" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[-0.28, 0.7, 0]}>
        <boxGeometry args={[0.16, 0.03, 0.16]} />
        <meshStandardMaterial color="#123" emissive="#1a6a44" emissiveIntensity={0.4} roughness={0.6} />
      </mesh>
      <mesh position={[-0.28, 0.86, 0]}>
        <sphereGeometry args={[0.1, 10, 10]} />
        <meshStandardMaterial color="#1d6b45" roughness={0.7} />
      </mesh>
      {([0.15, 0.28, 0.4] as const).map((z, i) => (
        <mesh key={z} position={[0.02, 0.46 + i * 0.035, z]}>
          <boxGeometry args={[0.42, 0.03, 0.28]} />
          <meshStandardMaterial color={i === 1 ? '#1a3a55' : '#121820'} roughness={0.6} />
        </mesh>
      ))}
    </group>
  )
}

function OfficeChair() {
  const spokes = [0, 1, 2, 3, 4]
  return (
    <group position={[0, 0, 1.16]}>
      <mesh position={[0, 0.28, 0]}>
        <cylinderGeometry args={[0.045, 0.05, 0.36, 12]} />
        <meshStandardMaterial color="#c5ccd8" metalness={0.85} roughness={0.22} />
      </mesh>
      {spokes.map((i) => {
        const a = (i / 5) * Math.PI * 2
        return (
          <group key={i} rotation={[0, a, 0]}>
            <mesh position={[0.18, 0.08, 0]}>
              <boxGeometry args={[0.32, 0.035, 0.05]} />
              <meshStandardMaterial color="#141820" metalness={0.5} roughness={0.4} />
            </mesh>
            <mesh position={[0.34, 0.05, 0]}>
              <sphereGeometry args={[0.045, 10, 10]} />
              <meshStandardMaterial color="#0c0e14" roughness={0.45} />
            </mesh>
          </group>
        )
      })}
      <mesh position={[0, 0.48, 0.02]}>
        <boxGeometry args={[0.62, 0.08, 0.58]} />
        <meshStandardMaterial color="#12151c" roughness={0.7} />
      </mesh>
      {/* Lumbar only — the pack and its cross stay visible above it. */}
      <mesh position={[0, 0.4, 0.2]}>
        <boxGeometry args={[0.46, 0.16, 0.05]} />
        <meshStandardMaterial color="#1c2433" roughness={0.6} />
      </mesh>
      {([-0.36, 0.36] as const).map((x) => (
        <group key={x}>
          <mesh position={[x, 0.68, 0.02]}>
            <boxGeometry args={[0.05, 0.28, 0.05]} />
            <meshStandardMaterial color="#1c222e" metalness={0.4} roughness={0.4} />
          </mesh>
          <mesh position={[x, 0.82, 0.04]}>
            <boxGeometry args={[0.08, 0.035, 0.32]} />
            <meshStandardMaterial color="#1c222e" metalness={0.4} roughness={0.4} />
          </mesh>
        </group>
      ))}
    </group>
  )
}

function WindowWall() {
  return (
    <group position={[0, 0, -3.55]}>
      {/* opaque surround */}
      <mesh position={[0, 3.28, 0]}>
        <boxGeometry args={[16, 0.28, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      <mesh position={[0, 0.38, 0]}>
        <boxGeometry args={[16, 0.76, 0.16]} />
        <meshStandardMaterial color="#3a455c" roughness={0.8} />
      </mesh>
      <mesh position={[-5.7, 1.9, 0]}>
        <boxGeometry args={[4.6, 2.7, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>
      <mesh position={[5.7, 1.9, 0]}>
        <boxGeometry args={[4.6, 2.7, 0.16]} />
        <meshStandardMaterial color={WALL} roughness={0.9} />
      </mesh>

      {/* curtain-wall frame */}
      <mesh position={[0, 0.78, 0.04]}>
        <boxGeometry args={[7.05, 0.08, 0.08]} />
        <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
      </mesh>
      <mesh position={[0, 3.12, 0.04]}>
        <boxGeometry args={[7.05, 0.08, 0.08]} />
        <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
      </mesh>
      {([-3.48, 3.48] as const).map((x) => (
        <mesh key={x} position={[x, 1.95, 0.04]}>
          <boxGeometry args={[0.08, 2.42, 0.08]} />
          <meshStandardMaterial color={FRAME} metalness={0.55} roughness={0.35} />
        </mesh>
      ))}
      {([-1.15, 1.15] as const).map((x) => (
        <mesh key={`m-${x}`} position={[x, 1.95, 0.07]}>
          <boxGeometry args={[0.045, 2.28, 0.05]} />
          <meshStandardMaterial color="#8b95a8" metalness={0.7} roughness={0.28} />
        </mesh>
      ))}

      {/* Clear glass. The city meshes sit outside this opening. */}
      <mesh position={[0, 1.95, 0.02]} raycast={() => null}>
        <planeGeometry args={[6.82, 2.26]} />
        <meshBasicMaterial
          color="#b7fff8"
          transparent
          opacity={0.06}
          depthWrite={false}
          side={DoubleSide}
          toneMapped={false}
        />
      </mesh>
      {/* faint glass sheen in front of the mullions' plane */}
      <mesh position={[0, 1.95, 0.09]} raycast={() => null}>
        <planeGeometry args={[6.82, 2.26]} />
        <meshBasicMaterial color="#b7fff8" transparent opacity={0.05} depthWrite={false} side={DoubleSide} />
      </mesh>

      {/* exterior sill */}
      <mesh position={[0, 0.72, -0.18]}>
        <boxGeometry args={[7.2, 0.06, 0.28]} />
        <meshStandardMaterial color="#0e1218" metalness={0.4} roughness={0.45} />
      </mesh>
    </group>
  )
}

function Desk() {
  return (
    <group>
      <mesh position={[0, 0.76, -0.15]}>
        <boxGeometry args={[3.7, 0.08, 1.45]} />
        <meshStandardMaterial color="#12151c" metalness={0.35} roughness={0.42} />
      </mesh>
      <mesh position={[0, 0.72, 0.52]}>
        <boxGeometry args={[3.7, 0.025, 0.04]} />
        <meshStandardMaterial color="#2de2e6" emissive="#2de2e6" emissiveIntensity={0.35} metalness={0.4} roughness={0.4} />
      </mesh>
      <mesh position={[0, 0.42, -0.72]}>
        <boxGeometry args={[3.55, 0.58, 0.06]} />
        <meshStandardMaterial color="#10141c" roughness={0.75} />
      </mesh>
      {([-1.55, 1.55] as const).map((x) => (
        <mesh key={x} position={[x, 0.38, 0.15]}>
          <boxGeometry args={[0.08, 0.72, 1.15]} />
          <meshStandardMaterial color="#1a1f2a" metalness={0.3} roughness={0.5} />
        </mesh>
      ))}
      <mesh position={[0.15, 0.81, 0.15]}>
        <boxGeometry args={[0.55, 0.02, 0.2]} />
        <meshStandardMaterial color="#0c0e14" roughness={0.5} />
      </mesh>
      <mesh position={[-1.5, 0.82, 0.15]} rotation={[-Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.13, 0.13, 0.045, 24]} />
        <meshStandardMaterial color="#c01028" emissive="#ff2040" emissiveIntensity={0.7} roughness={0.35} />
      </mesh>
    </group>
  )
}

function OfficeFloor() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0.7]}>
        <planeGeometry args={[16, 8.3]} />
        <meshStandardMaterial color="#12082a" roughness={0.72} metalness={0.12} side={DoubleSide} />
      </mesh>
      <gridHelper args={[8, 16, '#2de2e6', '#2a1060']} position={[0, 0.012, 0.55]} />
    </group>
  )
}

const HOME_POS: [number, number, number] = [0.15, 1.78, 3.35]
const HOME_TARGET: [number, number, number] = [0, 1.42, 0.05]

function DeskKit() {
  const mouse = useRef<Group>(null)
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (!mouse.current) return
    const pose = mouseHand(t)
    mouse.current.position.x = pose.x
    mouse.current.position.z = pose.z
    mouse.current.rotation.y = pose.yaw
  })
  const keys: [number, number][] = []
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 12; col++) {
      keys.push([col, row])
    }
  }
  return (
    <group>
      {/* keyboard in reach of the left hand */}
      <group position={[-0.3, KEY_TOP - 0.022, 0.34]}>
        <mesh>
          <boxGeometry args={[0.52, 0.02, 0.18]} />
          <meshStandardMaterial color="#2c3548" metalness={0.35} roughness={0.45} />
        </mesh>
        {keys.map(([col, row]) => (
          <mesh key={`${col}-${row}`} position={[-0.22 + col * 0.04, 0.016, -0.06 + row * 0.038]}>
            <boxGeometry args={[0.03, 0.012, 0.028]} />
            <meshStandardMaterial
              color={row === 0 ? '#d7fff8' : '#c5d0e0'}
              emissive={row === 0 ? '#2de2e6' : '#1a2433'}
              emissiveIntensity={row === 0 ? 0.45 : 0.15}
              metalness={0.2}
              roughness={0.4}
            />
          </mesh>
        ))}
      </group>
      {/* mouse pad + mouse under the right hand */}
      <mesh position={[0.48, 0.802, 0.4]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.28, 0.22]} />
        <meshStandardMaterial color="#10141c" roughness={0.8} />
      </mesh>
      <group ref={mouse} position={[0.48, MOUSE_TOP - 0.02, 0.4]}>
        <mesh>
          <boxGeometry args={[0.07, 0.028, 0.11]} />
          <meshStandardMaterial color="#d8fff8" emissive="#7ef9ff" emissiveIntensity={0.25} metalness={0.4} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.016, -0.01]}>
          <boxGeometry args={[0.028, 0.008, 0.04]} />
          <meshStandardMaterial color="#39ff14" emissive="#39ff14" emissiveIntensity={0.6} />
        </mesh>
      </group>
      {/* lamp over the right corner */}
      <group position={[1.42, 0.8, -0.42]}>
        <mesh position={[0, 0.02, 0]}>
          <cylinderGeometry args={[0.08, 0.1, 0.03, 16]} />
          <meshStandardMaterial color="#1c222e" metalness={0.6} roughness={0.35} />
        </mesh>
        <mesh position={[0, 0.28, 0]}>
          <cylinderGeometry args={[0.015, 0.015, 0.48, 8]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh position={[-0.16, 0.5, 0.08]} rotation={[0.4, 0, 0.9]}>
          <cylinderGeometry args={[0.012, 0.012, 0.36, 8]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.8} roughness={0.25} />
        </mesh>
        <mesh position={[-0.28, 0.42, 0.16]}>
          <coneGeometry args={[0.09, 0.08, 16, 1, true]} />
          <meshStandardMaterial color="#f4e2a8" emissive="#f9c80e" emissiveIntensity={0.55} side={DoubleSide} />
        </mesh>
      </group>
      <pointLight position={[1.05, 1.15, -0.05]} intensity={0.45} color="#ffe2a0" distance={2.4} />
      {/* mug and notebook */}
      <group position={[0.92, 0.84, 0.22]}>
        <mesh>
          <cylinderGeometry args={[0.045, 0.04, 0.07, 16]} />
          <meshStandardMaterial color="#101820" roughness={0.4} metalness={0.3} />
        </mesh>
        <mesh position={[0, 0.02, 0]}>
          <cylinderGeometry args={[0.038, 0.038, 0.02, 16]} />
          <meshStandardMaterial color="#3a2418" roughness={0.5} />
        </mesh>
        <mesh position={[0.055, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[0.022, 0.006, 6, 12]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.7} roughness={0.3} />
        </mesh>
      </group>
      <mesh position={[-1.35, 0.812, -0.15]} rotation={[-0.04, -0.4, 0]}>
        <boxGeometry args={[0.2, 0.012, 0.26]} />
        <meshStandardMaterial color="#1a2744" roughness={0.7} />
      </mesh>
      <mesh position={[-1.35, 0.82, -0.15]} rotation={[-0.04, -0.4, 0]}>
        <boxGeometry args={[0.16, 0.004, 0.2]} />
        <meshBasicMaterial color="#d7e6ff" />
      </mesh>
      {/* bin and rug */}
      <mesh position={[1.85, 0.16, 0.95]}>
        <cylinderGeometry args={[0.12, 0.1, 0.32, 12]} />
        <meshStandardMaterial color="#12151c" metalness={0.35} roughness={0.5} />
      </mesh>
      <mesh position={[0.05, 0.015, 1.15]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.85, 24]} />
        <meshStandardMaterial color="#1a1038" roughness={0.9} />
      </mesh>
      {/* coat rack by the door */}
      <group position={[-6.35, 0, 2.15]}>
        <mesh position={[0, 0.7, 0]}>
          <cylinderGeometry args={[0.03, 0.04, 1.4, 8]} />
          <meshStandardMaterial color="#2a3344" metalness={0.5} roughness={0.4} />
        </mesh>
        <mesh position={[0, 1.42, 0]}>
          <sphereGeometry args={[0.05, 10, 10]} />
          <meshStandardMaterial color="#c5ccd8" metalness={0.7} roughness={0.3} />
        </mesh>
        <mesh position={[0.08, 1.05, 0.02]} rotation={[0.15, 0, 0.2]}>
          <boxGeometry args={[0.28, 0.42, 0.06]} />
          <meshStandardMaterial color="#123044" roughness={0.6} />
        </mesh>
      </group>
    </group>
  )
}

export function OfficeScene({ bot, bots, desk, onOpenScreens }: Props) {
  const controls = useRef<OrbitControlsImpl>(null)
  const pose = useMemo(() => botPose(bot), [bot])

  const maps = useMemo(() => {
    const left = leftMonitorTexture(bot)
    const center = centerMonitorTexture(bot, desk)
    const right = rightMonitorTexture(bot)
    return { left, center, right }
  }, [bot, desk])

  useEffect(() => {
    return () => {
      maps.left.dispose()
      maps.center.dispose()
      maps.right.dispose()
    }
  }, [maps])

  useEffect(() => {
    const orbit = controls.current
    const cam = orbit?.object
    if (!orbit || !cam) return
    cam.position.set(...HOME_POS)
    orbit.target.set(...HOME_TARGET)
    orbit.update()
  }, [bot.id])

  return (
    <>
      <color attach="background" args={['#12082a']} />
      <fog attach="fog" args={['#14082e', 16, 62]} />
      <PerspectiveCamera makeDefault fov={46} near={0.08} far={80} position={HOME_POS} />
      <OrbitControls
        ref={controls}
        makeDefault
        target={HOME_TARGET}
        enableDamping
        dampingFactor={0.08}
        enablePan={false}
        minDistance={1.45}
        maxDistance={3.6}
        minPolarAngle={1.02}
        maxPolarAngle={1.75}
        minAzimuthAngle={-1.4}
        maxAzimuthAngle={1.4}
      />
      <ambientLight intensity={0.55} color="#c8b8ff" />
      <directionalLight position={[1.5, 4.2, 2]} intensity={0.65} color="#f2e8ff" />
      <pointLight position={[-1.15, 3.15, 0.4]} intensity={0.75} color="#7ef9ff" distance={8} />
      <pointLight position={[1.15, 3.15, 0.4]} intensity={0.75} color="#b967ff" distance={8} />
      <pointLight position={[0, 1.9, -2.4]} intensity={0.55} color="#2de2e6" distance={7} />
      <pointLight position={[0, 5.5, -10]} intensity={0.7} color="#9ecbff" distance={14} />

      <OfficeFloor />
      <Ceiling />
      <SideWall x={-7.9} rot={Math.PI / 2} />
      <SideWall x={7.9} rot={-Math.PI / 2} />
      <WallStockChart bot={bot} desk={desk} side="left" />
      <WallStockChart bot={bot} desk={desk} side="right" />
      <mesh position={[0, 1.69, 4.8]} rotation={[0, Math.PI, 0]}>
        <planeGeometry args={[16, 3.38]} />
        <meshStandardMaterial color="#160e2c" roughness={0.92} side={DoubleSide} />
      </mesh>
      <Door />
      <Credenza />
      <WindowWall />
      <StreetCity bots={bots && bots.length ? bots : [bot]} desk={desk} />
      <Desk />
      <DeskKit />
      <OfficeChair />

      <MonitorFrame position={[-1.55, 1.28, -0.62]} rotation={[0, 0.22, 0]} size={[1.02, 0.64]} edge="#39ff14" map={maps.left} onOpen={onOpenScreens} />
      <MonitorFrame position={[0.02, 1.4, -0.88]} rotation={[-0.08, 0, 0]} size={[1.22, 0.72]} edge="#2de2e6" map={maps.center} onOpen={onOpenScreens} />
      <MonitorFrame position={[1.58, 1.28, -0.62]} rotation={[0, -0.22, 0]} size={[1.02, 0.64]} edge="#39ff14" map={maps.right} onOpen={onOpenScreens} />

      <BotFigure pose={pose} deskWork />
      <NeonBloom strength={0.48} />
    </>
  )
}
