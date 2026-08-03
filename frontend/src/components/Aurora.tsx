// Fondo animado estilo "Aurora" (React Bits) — WebGL vía ogl, con vignette
// hacia el color de fondo del tema para que se funda con el contenido.
import { SoftAurora } from "@/components/SoftAurora"

export function Aurora() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden bg-background">
      <SoftAurora
        speed={0.5}
        scale={1.6}
        brightness={0.9}
        color1="#7c6cff"
        color2="#ff6ec7"
        noiseFrequency={2.2}
        noiseAmplitude={1.0}
        bandHeight={0.5}
        bandSpread={1.1}
        octaveDecay={0.12}
        layerOffset={2.5}
        colorSpeed={0.8}
        enableMouseInteraction
        mouseInfluence={0.2}
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,var(--background)_78%)]" />
    </div>
  )
}
