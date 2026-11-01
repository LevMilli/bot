import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'

/** Shared neon bloom — lighter pass so the plaza stays interactive on mid GPUs. */
export function NeonBloom({ strength = 1 }: { strength?: number }) {
  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <Bloom
        intensity={0.55 * strength}
        luminanceThreshold={0.38}
        luminanceSmoothing={0.45}
        mipmapBlur
        radius={0.45}
      />
      <Vignette offset={0.3} darkness={0.42} blendFunction={BlendFunction.NORMAL} />
    </EffectComposer>
  )
}
