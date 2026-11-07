import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'

/** Office/bank neon bloom only — city view skips this for frame rate. */
export function NeonBloom({
  strength = 1,
  /** Cheaper half-res path for the dense trading wing. */
  lite = false,
}: {
  strength?: number
  lite?: boolean
}) {
  return (
    <EffectComposer
      multisampling={0}
      enableNormalPass={false}
      resolutionScale={lite ? 0.35 : 1}
    >
      <Bloom
        intensity={(lite ? 0.28 : 0.4) * strength}
        luminanceThreshold={lite ? 0.6 : 0.45}
        luminanceSmoothing={0.55}
        mipmapBlur={!lite}
        radius={lite ? 0.18 : 0.35}
      />
      {!lite && (
        <Vignette offset={0.32} darkness={0.4} blendFunction={BlendFunction.NORMAL} />
      )}
    </EffectComposer>
  )
}
