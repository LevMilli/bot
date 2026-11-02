import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'

/** Office/bank neon bloom only — city view skips this for frame rate. */
export function NeonBloom({ strength = 1 }: { strength?: number }) {
  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <Bloom
        intensity={0.4 * strength}
        luminanceThreshold={0.45}
        luminanceSmoothing={0.5}
        mipmapBlur
        radius={0.35}
      />
      <Vignette offset={0.32} darkness={0.4} blendFunction={BlendFunction.NORMAL} />
    </EffectComposer>
  )
}
