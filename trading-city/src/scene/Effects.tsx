import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'

/** Shared neon bloom — matches reference beam / vault glow without washing labels. */
export function NeonBloom({ strength = 1 }: { strength?: number }) {
  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <Bloom
        intensity={1.15 * strength}
        luminanceThreshold={0.18}
        luminanceSmoothing={0.4}
        mipmapBlur
        radius={0.72}
      />
      <Vignette offset={0.22} darkness={0.55} blendFunction={BlendFunction.NORMAL} />
    </EffectComposer>
  )
}
