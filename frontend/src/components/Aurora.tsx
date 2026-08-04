import { useEffect, useRef } from "react"
import { Color, Mesh, Program, Renderer, Triangle } from "ogl"

const VERT = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`

const FRAG = `#version 300 es
precision highp float;

uniform float uTime;
uniform float uAmplitude;
uniform vec3 uColorStops[3];
uniform vec2 uResolution;
uniform float uBlend;

out vec4 fragColor;

vec3 permute(vec3 x) {
  return mod(((x * 34.0) + 1.0) * x, 289.0);
}

float snoise(vec2 v){
  const vec4 C = vec4(
      0.211324865405187, 0.366025403784439,
      -0.577350269189626, 0.024390243902439
  );
  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);

  vec3 p = permute(
      permute(i.y + vec3(0.0, i1.y, 1.0))
    + i.x + vec3(0.0, i1.x, 1.0)
  );

  vec3 m = max(
      0.5 - vec3(
          dot(x0, x0),
          dot(x12.xy, x12.xy),
          dot(x12.zw, x12.zw)
      ),
      0.0
  );
  m = m * m;
  m = m * m;

  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);

  vec3 g;
  g.x  = a0.x  * x0.x  + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

struct ColorStop {
  vec3 color;
  float position;
};

#define COLOR_RAMP(colors, factor, finalColor) {              \
  int index = 0;                                            \
  for (int i = 0; i < 2; i++) {                               \
     ColorStop currentColor = colors[i];                    \
     bool isInBetween = currentColor.position <= factor;    \
     index = int(mix(float(index), float(i), float(isInBetween))); \
  }                                                         \
  ColorStop currentColor = colors[index];                   \
  ColorStop nextColor = colors[index + 1];                  \
  float range = nextColor.position - currentColor.position; \
  float lerpFactor = (factor - currentColor.position) / range; \
  finalColor = mix(currentColor.color, nextColor.color, lerpFactor); \
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution;

  ColorStop colors[3];
  colors[0] = ColorStop(uColorStops[0], 0.0);
  colors[1] = ColorStop(uColorStops[1], 0.5);
  colors[2] = ColorStop(uColorStops[2], 1.0);

  vec3 rampColor;
  COLOR_RAMP(colors, uv.x, rampColor);

  float height = snoise(vec2(uv.x * 2.0 + uTime * 0.1, uTime * 0.25)) * 0.5 * uAmplitude;
  height = exp(height);
  height = (uv.y * 2.0 - height + 0.2);
  float intensity = 0.6 * height;

  float midPoint = 0.20;
  float auroraAlpha = smoothstep(midPoint - uBlend * 0.5, midPoint + uBlend * 0.5, intensity);

  vec3 auroraColor = intensity * rampColor;

  fragColor = vec4(auroraColor * auroraAlpha, auroraAlpha);
}
`

export interface AuroraProps {
  colorStops?: [string, string, string]
  speed?: number
  blend?: number
  amplitude?: number
  /** Cap en device-pixel-ratio para no sobrecargar la GPU en pantallas HiDPI. */
  maxDpr?: number
  /** Techo de fps del loop de render (evita competir por el hilo principal). */
  targetFps?: number
}

/**
 * Fondo WebGL minimalista (misma familia visual que el Plasma que reemplaza:
 * README §Fondo Plasma). Aplica las mismas guardas de rendimiento: se pausa
 * fuera de viewport, con la pestaña oculta o si el usuario pide reduced-motion,
 * y limita DPR/fps para no competir por GPU/batería en equipos modestos.
 */
export function Aurora({
  colorStops = ["#3A29FF", "#FF94B4", "#FF3232"],
  speed = 1.0,
  blend = 0.5,
  amplitude = 1.0,
  maxDpr = 1.5,
  targetFps = 30,
}: AuroraProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const propsRef = useRef({ colorStops, speed, blend, amplitude })
  propsRef.current = { colorStops, speed, blend, amplitude }

  useEffect(() => {
    const containerEl = containerRef.current
    if (!containerEl) return

    const prefersReducedMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches

    let renderer: Renderer
    try {
      renderer = new Renderer({
        alpha: true,
        premultipliedAlpha: true,
        antialias: false,
        dpr: Math.min(window.devicePixelRatio || 1, maxDpr),
      })
    } catch {
      return
    }
    const gl = renderer.gl
    if (!gl) return
    gl.clearColor(0, 0, 0, 0)
    gl.enable(gl.BLEND)
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)
    const canvas = gl.canvas
    canvas.style.display = "block"
    canvas.style.width = "100%"
    canvas.style.height = "100%"
    containerEl.appendChild(canvas)

    const toRgb = (hex: string) => {
      const c = new Color(hex)
      return [c.r, c.g, c.b]
    }

    const program = new Program(gl, {
      vertex: VERT,
      fragment: FRAG,
      uniforms: {
        uTime: { value: 0 },
        uAmplitude: { value: amplitude },
        uColorStops: { value: colorStops.map(toRgb) },
        uResolution: { value: new Float32Array([1, 1]) },
        uBlend: { value: blend },
      },
    })
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program })

    let resizePending = false
    const setSize = () => {
      const rect = containerEl.getBoundingClientRect()
      renderer.setSize(Math.max(1, Math.floor(rect.width)), Math.max(1, Math.floor(rect.height)))
      canvas.style.width = "100%"
      canvas.style.height = "100%"
      const res = program.uniforms.uResolution.value as Float32Array
      res[0] = gl.drawingBufferWidth
      res[1] = gl.drawingBufferHeight
    }
    const ro = new ResizeObserver(() => {
      if (resizePending) return
      resizePending = true
      requestAnimationFrame(() => {
        resizePending = false
        setSize()
      })
    })
    ro.observe(containerEl)
    setSize()

    let raf = 0
    let contextLost = false
    let isVisible = true
    let tabVisible = document.visibilityState !== "hidden"
    const t0 = performance.now()
    const frameInterval = 1000 / targetFps
    let lastFrameTime = 0

    const loop = (t: number) => {
      if (contextLost || !isVisible || !tabVisible) return
      if (t - lastFrameTime < frameInterval) {
        raf = requestAnimationFrame(loop)
        return
      }
      lastFrameTime = t
      const { speed: liveSpeed, amplitude: liveAmplitude, blend: liveBlend, colorStops: liveStops } =
        propsRef.current
      program.uniforms.uTime.value = (t - t0) * 0.001 * liveSpeed * 0.1
      program.uniforms.uAmplitude.value = liveAmplitude
      program.uniforms.uBlend.value = liveBlend
      program.uniforms.uColorStops.value = liveStops.map(toRgb)
      renderer.render({ scene: mesh })
      raf = requestAnimationFrame(loop)
    }

    const onLost = (e: Event) => {
      e.preventDefault()
      contextLost = true
      cancelAnimationFrame(raf)
    }
    const onRestored = () => {
      contextLost = false
      if (isVisible && tabVisible && !prefersReducedMotion) {
        cancelAnimationFrame(raf)
        raf = requestAnimationFrame(loop)
      }
    }
    canvas.addEventListener("webglcontextlost", onLost)
    canvas.addEventListener("webglcontextrestored", onRestored)

    const io = new IntersectionObserver(
      ([entry]) => {
        const was = isVisible
        isVisible = entry.isIntersecting
        if (isVisible && !was && !contextLost && tabVisible && !prefersReducedMotion) {
          cancelAnimationFrame(raf)
          raf = requestAnimationFrame(loop)
        }
      },
      { threshold: 0 }
    )
    io.observe(containerEl)

    const onVis = () => {
      tabVisible = document.visibilityState !== "hidden"
      if (tabVisible && isVisible && !contextLost && !prefersReducedMotion) {
        cancelAnimationFrame(raf)
        lastFrameTime = 0
        raf = requestAnimationFrame(loop)
      } else {
        cancelAnimationFrame(raf)
      }
    }
    document.addEventListener("visibilitychange", onVis)

    if (prefersReducedMotion) {
      renderer.render({ scene: mesh })
    } else {
      raf = requestAnimationFrame(loop)
    }

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      io.disconnect()
      document.removeEventListener("visibilitychange", onVis)
      canvas.removeEventListener("webglcontextlost", onLost)
      canvas.removeEventListener("webglcontextrestored", onRestored)
      try {
        containerEl.removeChild(canvas)
      } catch {
        // ya desmontado
      }
      gl.getExtension("WEBGL_lose_context")?.loseContext()
    }
  }, [maxDpr, targetFps])

  return <div ref={containerRef} className="relative size-full overflow-hidden" />
}
