export function GridFloor({ size = 80 }: { size?: number }) {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
        <planeGeometry args={[size, size]} />
        <meshStandardMaterial color="#050014" roughness={0.95} metalness={0.1} />
      </mesh>
      <gridHelper
        args={[size, size, '#1a6cff', '#0a2a66']}
        position={[0, 0.02, 0]}
      />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
        <ringGeometry args={[18, 18.15, 64]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.35} />
      </mesh>
    </group>
  )
}
