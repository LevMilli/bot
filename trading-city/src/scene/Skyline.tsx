import { useMemo } from 'react'
import * as THREE from 'three'

function rand(seed: number) {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

export function Skyline({ z = -26, width = 78 }: { z?: number; width?: number }) {
  const blocks = useMemo(() => {
    const out: { x: number; h: number; w: number; d: number; windows: [number, number, number][] }[] = []
    let x = -width / 2
    let i = 0
    while (x < width / 2) {
      const w = 0.7 + rand(i + 1) * 2.4
      const h = 2.2 + rand(i + 7) * 11
      const d = 0.7 + rand(i + 3) * 1.8
      const windows: [number, number, number][] = []
      // Sparse lit windows — dense per-window meshes crushed city FPS.
      for (let wy = 0.55; wy < h - 0.35; wy += 0.95) {
        if (rand(i * 17 + wy * 3) > 0.45) {
          windows.push([(w / 2 - 0.08) * (rand(i + wy) > 0.5 ? 1 : -1), wy - h / 2, d / 2 + 0.02])
        }
        if (rand(i * 9 + wy) > 0.62) {
          windows.push([(rand(i + wy) - 0.5) * (w - 0.3), wy - h / 2, d / 2 + 0.02])
        }
      }
      out.push({ x: x + w / 2, h, w, d, windows })
      x += w + 0.1 + rand(i + 5) * 0.3
      i += 1
    }
    return out
  }, [width])

  return (
    <group position={[0, 0, z]}>
      {blocks.map((b, i) => (
        <group key={i} position={[b.x, b.h / 2, 0]}>
          <mesh>
            <boxGeometry args={[b.w, b.h, b.d]} />
            <meshStandardMaterial color="#05040f" roughness={0.92} metalness={0.05} />
          </mesh>
          {b.windows.map((p, wi) => (
            <mesh key={wi} position={p}>
              <boxGeometry args={[0.1, 0.1, 0.04]} />
              <meshBasicMaterial color={rand(i + wi) > 0.72 ? '#39ff14' : '#f9c80e'} />
            </mesh>
          ))}
        </group>
      ))}
    </group>
  )
}

export function Starfield({ count = 900 }: { count?: number }) {
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 140
      arr[i * 3 + 1] = 6 + Math.random() * 48
      arr[i * 3 + 2] = -8 - Math.random() * 70
    }
    return arr
  }, [count])

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#e8f0ff" size={0.055} sizeAttenuation transparent opacity={0.9} />
    </points>
  )
}

export function SkyEquityLine() {
  const curve = useMemo(() => {
    const pts = [
      new THREE.Vector3(-28, 10.5, -21),
      new THREE.Vector3(-20, 12.2, -21),
      new THREE.Vector3(-12, 9.4, -21),
      new THREE.Vector3(-5, 13.5, -21),
      new THREE.Vector3(1, 11.2, -21),
      new THREE.Vector3(7, 15.2, -21),
      new THREE.Vector3(14, 12.8, -21),
      new THREE.Vector3(22, 16.4, -21),
      new THREE.Vector3(28, 13.6, -21),
    ]
    return new THREE.CatmullRomCurve3(pts)
  }, [])
  const geom = useMemo(() => new THREE.TubeGeometry(curve, 96, 0.055, 8, false), [curve])
  const soft = useMemo(() => new THREE.TubeGeometry(curve, 96, 0.14, 8, false), [curve])
  return (
    <group>
      <mesh geometry={soft}>
        <meshBasicMaterial color="#c8d8ff" transparent opacity={0.18} depthWrite={false} />
      </mesh>
      <mesh geometry={geom}>
        <meshBasicMaterial color="#f4f7ff" transparent opacity={0.92} />
      </mesh>
    </group>
  )
}

/** Soft purple horizon wash behind the skyline. */
export function PurpleHorizon() {
  return (
    <group>
      <mesh position={[0, 14, -40]}>
        <planeGeometry args={[180, 55]} />
        <meshBasicMaterial color="#1c0642" transparent opacity={0.7} depthWrite={false} />
      </mesh>
      <mesh position={[0, 4, -38]}>
        <planeGeometry args={[180, 18]} />
        <meshBasicMaterial color="#3a1280" transparent opacity={0.35} depthWrite={false} />
      </mesh>
    </group>
  )
}
