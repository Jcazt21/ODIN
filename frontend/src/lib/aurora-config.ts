// ─────────────────────────────────────────────────────────────────────────────
// Parámetros del fondo <SoftAurora /> (el panel "Customize" de React Bits).
// Este archivo es la ÚNICA fuente de verdad: tocar los números de aquí cambia
// el fondo del login y del workspace a la vez.
// ─────────────────────────────────────────────────────────────────────────────
import type { SoftAuroraProps } from "@/components/SoftAurora"

export type Theme = "light" | "dark"

/**
 * Colores heredados de la Aurora anterior (morado en claro, teal/violeta en
 * oscuro). `color1` tiñe la primera capa, `color2` la segunda.
 */
export const SOFT_AURORA_COLORS: Record<Theme, { color1: string; color2: string }> = {
  light: { color1: "#B497CF", color2: "#6200EE" },
  dark: { color1: "#03DAC6", color2: "#5227FF" },
}

/** Parámetros compartidos por ambos temas (los sliders del panel Customize). */
export const SOFT_AURORA_PARAMS = {
  speed: 0.6, // velocidad global de la animación
  scale: 1.5, // escala del patrón de ruido
  brightness: 1.0, // brillo global
  noiseFrequency: 2.5, // frecuencia base del Perlin
  noiseAmplitude: 1.0, // amplitud base del Perlin
  bandHeight: 0.5, // posición vertical de la banda (0-1)
  bandSpread: 1.0, // dispersión vertical del glow
  octaveDecay: 0.1, // decaimiento de amplitud por octava
  layerOffset: 0, // desfase temporal entre las dos capas
  colorSpeed: 1.0, // velocidad del corrimiento de paleta
  enableMouseInteraction: false, // reacción al cursor
  mouseInfluence: 0.25, // fuerza del desplazamiento por cursor
} as const satisfies SoftAuroraProps

/**
 * Ajustes por tema. El shader compone de forma aditiva y saca su alpha de la
 * longitud del color (`alpha = length(col)`), así que en claro —sobre un fondo
 * casi blanco— un color pálido apenas registra y el fondo se lava. Se compensa
 * subiendo el brillo; en oscuro la aurora ya destaca sola.
 */
const SOFT_AURORA_THEME_PARAMS: Record<Theme, Partial<SoftAuroraProps>> = {
  light: { brightness: 1.7 },
  dark: {},
}

/** Opacidad del fondo por pantalla y tema (el efecto no debe tapar el texto). */
export const SOFT_AURORA_OPACITY: Record<"login" | "workspace", Record<Theme, number>> = {
  login: { light: 0.8, dark: 0.62 },
  workspace: { light: 0.7, dark: 0.55 },
}

/**
 * Presupuesto de render, y el knob de rendimiento más importante de la app.
 *
 * `maxDpr`: el fragment shader es caro (2 capas x 3 octavas de Perlin 3D = 48
 * hashes por píxel) y el fondo cubre todo el viewport. Como el resultado es un
 * degradado suave, renderizar por debajo de resolución nativa y dejar que el
 * navegador reescale es imperceptible, y 0.7 cuesta ~4x menos que 1.5.
 *
 * `targetFps`: además del render propio, cada frame nuevo del fondo invalida
 * el backdrop-filter de todas las superficies .odin-glass encima. Bajar los
 * fps divide ese trabajo de desenfoque en la misma proporción; a 20 fps la
 * aurora sigue viéndose fluida porque se mueve muy lento.
 */
export const SOFT_AURORA_QUALITY = {
  maxDpr: 0.7,
  targetFps: 20,
} as const satisfies SoftAuroraProps

/** Props listos para `<SoftAurora {...softAuroraFor(theme)} />`. */
export function softAuroraFor(theme: Theme): SoftAuroraProps {
  return {
    ...SOFT_AURORA_PARAMS,
    ...SOFT_AURORA_QUALITY,
    ...SOFT_AURORA_COLORS[theme],
    ...SOFT_AURORA_THEME_PARAMS[theme],
  }
}
