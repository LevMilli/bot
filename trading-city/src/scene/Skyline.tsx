import { useMemo } from 'react'

function rand(seed: number) {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

export function Skyline({ z = -28, width = 70 }: { z?: number; width?: number }) {
  const blocks = useMemo(() => {
    const out: { x: number; h: number; w: number; d: number; glow: boolean }[] = []
    let x = -width / 2
    let i = 0
    while (x < width / 2) {
      const w = 0.8 + rand(i + 1) * 2.2
      const h = 2 + rand(i + 7) * 10
      const d = 0.8 + rand(i + 3) * 1.6
      out.push({ x: x + w / 2, h, w, d, glow: rand(i + 11) > 0.55 })
      x += w + 0.15 + rand(i + 5) * 0.4
      i += 1
    }
    return out
  }, [width])

  return (
    <group position={[0, 0, z]}>
      {blocks.map((b, i) => (
        <mesh key={i} position={[b.x, b.h / 2, 0]}>
          <boxGeometry args={[b.w, b.h, b.d]} />
          <meshStandardMaterial
            color="#07041a"
            emissive={b.glow ? '#f9c80e' : '#1a1040'}
            emissiveIntensity={b.glow ? 0.35 : 0.08}
            roughness={0.85}
          />
        </mesh>
      ))}
    </group>
  )
}
