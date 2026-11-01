export function GridFloor({ size = 90, cell = 1 }: { size?: number; cell?: number }) {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <planeGeometry args={[size, size]} />
        <meshStandardMaterial color="#020010" roughness={1} metalness={0} />
      </mesh>
      {/* Bright cyan synthwave grid */}
      <gridHelper args={[size, Math.floor(size / cell), '#1ec8ff', '#0a4cff']} position={[0, 0.01, 0]} />
      <gridHelper
        args={[size, Math.floor(size / (cell * 5)), '#4de8ff', '#0830a0']}
        position={[0, 0.02, 0]}
      />
      {/* Plaza ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.04, -1]}>
        <ringGeometry args={[11.2, 11.45, 96]} />
        <meshBasicMaterial color="#2de2e6" transparent opacity={0.85} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.035, -1]}>
        <ringGeometry args={[11.5, 11.7, 96]} />
        <meshBasicMaterial color="#7ef9ff" transparent opacity={0.35} />
      </mesh>
    </group>
  )
}
