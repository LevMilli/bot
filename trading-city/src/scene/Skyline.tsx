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
      for (let wy = 0.45; wy < h - 0.3; wy += 0.55) {
        for (let side = -1; side <= 1; side += 2) {
          if (rand(i * 17 + wy * 3 + side) > 0.42) {
            windows.push([(w / 2 - 0.08) * side, wy - h / 2, d / 2 + 0.02])
          }
        }
        if (rand(i * 9 + wy) > 0.5) {
          windows.push([(rand(i + wy) - 0.5) * (w - 0.3), wy - h / 2, d / 2 + 0.02])
        }
      }
      out.push({ x: x + w / 2, h, w, d, windows })
      x += w + 0.12 + rand(i + 5) * 0.35
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
              <boxGeometry args={[0.11, 0.11, 0.04]} />
              <meshBasicMaterial color={rand(i + wi) > 0.7 ? '#39ff14' : '#f9c80e'} />
            </mesh>
          ))}
        </group>
      ))}
    </group>
  )
}

export function Starfield({ count = 500 }: { count?: number }) {
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 120
      arr[i * 3 + 1] = 8 + Math.random() * 40
      arr[i * 3 + 2] = -20 - Math.random() * 60
    }
    return arr
  }, [count])

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#e8f0ff" size={0.08} sizeAttenuation transparent opacity={0.85} />
    </points>
  )
}

export function SkyEquityLine() {
  const curve = useMemo(() => {
    const pts = [
      new THREE.Vector3(-22, 9, -24),
      new THREE.Vector3(-12, 11, -24),
      new THREE.Vector3(-4, 8.5, -24),
      new THREE.Vector3(2, 12, -24),
      new THREE.Vector3(8, 10, -24),
      new THREE.Vector3(14, 14, -24),
      new THREE.Vector3(22, 11, -24),
    ]
    return new THREE.CatmullRomCurve3(pts)
  }, [])
  const geom = useMemo(() => new THREE.TubeGeometry(curve, 64, 0.045, 6, false), [curve])
  return (
    <mesh geometry={geom}>
      <meshBasicMaterial color="#f4f7ff" transparent opacity={0.75} />
    </mesh>
  )
}
