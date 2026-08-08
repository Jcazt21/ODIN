import { useEffect, useRef } from "react"
import { Mesh, Program, Renderer, Triangle } from "ogl"

const VERT = `
attribute vec2 uv;
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`

const FRAG = `
precision highp float;

uniform float uTime;
uniform vec3 uResolution;
uniform float uSpeed;
uniform float uScale;
uniform float uBrightness;
uniform vec3 uColor1;
uniform vec3 uColor2;
uniform float uNoiseFreq;
uniform float uNoiseAmp;
uniform float uBandHeight;
uniform float uBandSpread;
uniform float uOctaveDecay;
uniform float uLayerOffset;
uniform float uColorSpeed;
uniform vec2 uMouse;
uniform float uMouseInfluence;
uniform bool uEnableMouse;

#define TAU 6.28318

vec3 gradientHash(vec3 p) {
  p = vec3(
    dot(p, vec3(127.1, 311.7, 234.6)),
    dot(p, vec3(269.5, 183.3, 198.3)),
    dot(p, vec3(169.5, 283.3, 156.9))
  );
  vec3 h = fract(sin(p) * 43758.5453123);
  float phi = acos(2.0 * h.x - 1.0);
  float theta = TAU * h.y;
  return vec3(cos(theta) * sin(phi), sin(theta) * cos(phi), cos(phi));
}

float quinticSmooth(float t) {
  float t2 = t * t;
  float t3 = t * t2;
  return 6.0 * t3 * t2 - 15.0 * t2 * t2 + 10.0 * t3;
}

vec3 cosineGradient(float t, vec3 a, vec3 b, vec3 c, vec3 d) {
  return a + b * cos(TAU * (c * t + d));
}

float perlin3D(float amplitude, float frequency, float px, float py, float pz) {
  float x = px * frequency;
  float y = py * frequency;

  float fx = floor(x); float fy = floor(y); float fz = floor(pz);
  float cx = ceil(x);  float cy = ceil(y);  float cz = ceil(pz);

  vec3 g000 = gradientHash(vec3(fx, fy, fz));
  vec3 g100 = gradientHash(vec3(cx, fy, fz));
  vec3 g010 = gradientHash(vec3(fx, cy, fz));
  vec3 g110 = gradientHash(vec3(cx, cy, fz));
  vec3 g001 = gradientHash(vec3(fx, fy, cz));
  vec3 g101 = gradientHash(vec3(cx, fy, cz));
  vec3 g011 = gradientHash(vec3(fx, cy, cz));
  vec3 g111 = gradientHash(vec3(cx, cy, cz));

  float d000 = dot(g000, vec3(x - fx, y - fy, pz - fz));
  float d100 = dot(g100, vec3(x - cx, y - fy, pz - fz));
  float d010 = dot(g010, vec3(x - fx, y - cy, pz - fz));
  float d110 = dot(g110, vec3(x - cx, y - cy, pz - fz));
  float d001 = dot(g001, vec3(x - fx, y - fy, pz - cz));
  float d101 = dot(g101, vec3(x - cx, y - fy, pz - cz));
  float d011 = dot(g011, vec3(x - fx, y - cy, pz - cz));
  float d111 = dot(g111, vec3(x - cx, y - cy, pz - cz));

  float sx = quinticSmooth(x - fx);
  float sy = quinticSmooth(y - fy);
  float sz = quinticSmooth(pz - fz);

  float lx00 = mix(d000, d100, sx);
  float lx10 = mix(d010, d110, sx);
  float lx01 = mix(d001, d101, sx);
  float lx11 = mix(d011, d111, sx);

  float ly0 = mix(lx00, lx10, sy);
  float ly1 = mix(lx01, lx11, sy);

  return amplitude * mix(ly0, ly1, sz);
}

float auroraGlow(float t, vec2 shift) {
  vec2 uv = gl_FragCoord.xy / uResolution.y;
  uv += shift;

  float noiseVal = 0.0;
  float freq = uNoiseFreq;
  float amp = uNoiseAmp;
  vec2 samplePos = uv * uScale;

  for (float i = 0.0; i < 3.0; i += 1.0) {
    noiseVal += perlin3D(amp, freq, samplePos.x, samplePos.y, t);
    amp *= uOctaveDecay;
    freq *= 2.0;
  }

  float yBand = uv.y * 10.0 - uBandHeight * 10.0;
  return 0.3 * max(exp(uBandSpread * (1.0 - 1.1 * abs(noiseVal + yBand))), 0.0);
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  float t = uSpeed * 0.4 * uTime;

  vec2 shift = vec2(0.0);
  if (uEnableMouse) {
    shift = (uMouse - 0.5) * uMouseInfluence;
  }

  vec3 col = vec3(0.0);
  col += 0.99 * auroraGlow(t, shift) * cosineGradient(uv.x + uTime * uSpeed * 0.2 * uColorSpeed, vec3(0.5), vec3(0.5), vec3(1.0), vec3(0.3, 0.20, 0.20)) * uColor1;
  col += 0.99 * auroraGlow(t + uLayerOffset, shift) * cosineGradient(uv.x + uTime * uSpeed * 0.1 * uColorSpeed, vec3(0.5), vec3(0.5), vec3(2.0, 1.0, 0.0), vec3(0.5, 0.20, 0.25)) * uColor2;

  col *= uBrightness;
  float alpha = clamp(length(col), 0.0, 1.0);
  gl_FragColor = vec4(col, alpha);
}
`

function hexToVec3(hex: string): [number, number, number] {
  const h = hex.replace("#", "")
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ]
}

export interface SoftAuroraProps {
  /** Multiplicador global de velocidad de animación. */
  speed?: number
  /** Escala del patrón de ruido. */
  scale?: number
  /** Multiplicador global de brillo. */
  brightness?: number
  /** Tinte de la primera capa de aurora. */
  color1?: string
  /** Tinte de la segunda capa de aurora. */
  color2?: string
  /** Frecuencia base del ruido Perlin. */
  noiseFrequency?: number
  /** Amplitud base del ruido Perlin. */
  noiseAmplitude?: number
  /** Posición vertical de la banda (0-1). */
  bandHeight?: number
  /** Dispersión vertical del glow. */
  bandSpread?: number
  /** Decaimiento de amplitud por octava de ruido. */
  octaveDecay?: number
  /** Desfase temporal entre las dos capas. */
  layerOffset?: number
  /** Velocidad del desplazamiento de paleta. */
  colorSpeed?: number
  /** Habilita el desplazamiento reactivo al cursor. */
  enableMouseInteraction?: boolean
  /** Fuerza del desplazamiento por cursor. */
  mouseInfluence?: number
  /** Cap en device-pixel-ratio para no sobrecargar la GPU en pantallas HiDPI. */
  maxDpr?: number
  /** Techo de fps del loop de render (evita competir por el hilo principal). */
  targetFps?: number
}

/**
 * Fondo WebGL de aurora suave (React Bits <SoftAurora />, portado a TS).
 * Mantiene las guardas de rendimiento del fondo anterior: se pausa fuera de
 * viewport, con la pestaña oculta o si el usuario pide reduced-motion, y limita
 * DPR/fps para no competir por GPU/batería en equipos modestos.
 *
 * Los parámetros por defecto viven en `@/lib/aurora-config`; aquí solo están los
 * fallbacks del componente.
 */
export function SoftAurora({
  speed = 0.6,
  scale = 1.5,
  brightness = 1.0,
  color1 = "#f7f7f7",
  color2 = "#e100ff",
  noiseFrequency = 2.5,
  noiseAmplitude = 1.0,
  bandHeight = 0.5,
  bandSpread = 1.0,
  octaveDecay = 0.1,
  layerOffset = 0,
  colorSpeed = 1.0,
  enableMouseInteraction = false,
  mouseInfluence = 0.25,
  maxDpr = 1.5,
  targetFps = 30,
}: SoftAuroraProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  // Los props se leen vivos dentro del loop: cambiar tema (o cualquier
  // parámetro) no debe recrear el contexto WebGL.
  const propsRef = useRef({
    speed,
    scale,
    brightness,
    color1,
    color2,
    noiseFrequency,
    noiseAmplitude,
    bandHeight,
    bandSpread,
    octaveDecay,
    layerOffset,
    colorSpeed,
    enableMouseInteraction,
    mouseInfluence,
  })
  propsRef.current = {
    speed,
    scale,
    brightness,
    color1,
    color2,
    noiseFrequency,
    noiseAmplitude,
    bandHeight,
    bandSpread,
    octaveDecay,
    layerOffset,
    colorSpeed,
    enableMouseInteraction,
    mouseInfluence,
  }

  useEffect(() => {
    const containerEl = containerRef.current
    if (!containerEl) return

    const prefersReducedMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches

    let renderer: Renderer
    try {
      renderer = new Renderer({
        alpha: true,
        premultipliedAlpha: false,
        antialias: false,
        dpr: Math.min(window.devicePixelRatio || 1, maxDpr),
      })
    } catch {
      return
    }
    const gl = renderer.gl
    if (!gl) return
    gl.clearColor(0, 0, 0, 0)
    const canvas = gl.canvas
    canvas.style.display = "block"
    canvas.style.width = "100%"
    canvas.style.height = "100%"
    containerEl.appendChild(canvas)

    const p = propsRef.current
    const program = new Program(gl, {
      vertex: VERT,
      fragment: FRAG,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new Float32Array([1, 1, 1]) },
        uSpeed: { value: p.speed },
        uScale: { value: p.scale },
        uBrightness: { value: p.brightness },
        uColor1: { value: hexToVec3(p.color1) },
        uColor2: { value: hexToVec3(p.color2) },
        uNoiseFreq: { value: p.noiseFrequency },
        uNoiseAmp: { value: p.noiseAmplitude },
        uBandHeight: { value: p.bandHeight },
        uBandSpread: { value: p.bandSpread },
        uOctaveDecay: { value: p.octaveDecay },
        uLayerOffset: { value: p.layerOffset },
        uColorSpeed: { value: p.colorSpeed },
        uMouse: { value: new Float32Array([0.5, 0.5]) },
        uMouseInfluence: { value: p.mouseInfluence },
        uEnableMouse: { value: p.enableMouseInteraction },
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
      res[2] = gl.drawingBufferWidth / Math.max(1, gl.drawingBufferHeight)
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

    // El contenedor es pointer-events:none (es un fondo), así que el cursor se
    // sigue a nivel window y se normaliza contra el rect del canvas.
    let currentMouse: [number, number] = [0.5, 0.5]
    let targetMouse: [number, number] = [0.5, 0.5]
    const onPointerMove = (e: PointerEvent) => {
      if (!propsRef.current.enableMouseInteraction) return
      const rect = canvas.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) return
      targetMouse = [
        (e.clientX - rect.left) / rect.width,
        1.0 - (e.clientY - rect.top) / rect.height,
      ]
    }
    window.addEventListener("pointermove", onPointerMove, { passive: true })

    let raf = 0
    let contextLost = false
    let isVisible = true
    let tabVisible = document.visibilityState !== "hidden"
    const t0 = performance.now()
    const frameInterval = 1000 / targetFps
    let lastFrameTime = 0

    const applyUniforms = (elapsedSeconds: number) => {
      const live = propsRef.current
      const u = program.uniforms
      u.uTime.value = elapsedSeconds
      u.uSpeed.value = live.speed
      u.uScale.value = live.scale
      u.uBrightness.value = live.brightness
      u.uColor1.value = hexToVec3(live.color1)
      u.uColor2.value = hexToVec3(live.color2)
      u.uNoiseFreq.value = live.noiseFrequency
      u.uNoiseAmp.value = live.noiseAmplitude
      u.uBandHeight.value = live.bandHeight
      u.uBandSpread.value = live.bandSpread
      u.uOctaveDecay.value = live.octaveDecay
      u.uLayerOffset.value = live.layerOffset
      u.uColorSpeed.value = live.colorSpeed
      u.uMouseInfluence.value = live.mouseInfluence
      u.uEnableMouse.value = live.enableMouseInteraction

      const mouse = u.uMouse.value as Float32Array
      if (live.enableMouseInteraction) {
        currentMouse[0] += 0.05 * (targetMouse[0] - currentMouse[0])
        currentMouse[1] += 0.05 * (targetMouse[1] - currentMouse[1])
        mouse[0] = currentMouse[0]
        mouse[1] = currentMouse[1]
      } else {
        currentMouse = [0.5, 0.5]
        mouse[0] = 0.5
        mouse[1] = 0.5
      }
    }

    const loop = (t: number) => {
      if (contextLost || !isVisible || !tabVisible) return
      if (t - lastFrameTime < frameInterval) {
        raf = requestAnimationFrame(loop)
        return
      }
      lastFrameTime = t
      applyUniforms((t - t0) * 0.001)
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
      applyUniforms(0)
      renderer.render({ scene: mesh })
    } else {
      raf = requestAnimationFrame(loop)
    }

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      io.disconnect()
      window.removeEventListener("pointermove", onPointerMove)
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
