// Etiquetas legibles para los enums que expone el backend (api-types.ts es la
// fuente de verdad de los valores; esto solo traduce a español para mostrar).
// Unifica los mapas que antes estaban duplicados en App.tsx y ReportsList.tsx.

export const SENTIMENT_LABELS: Record<string, string> = {
  POS: "Positivo",
  NEG: "Negativo",
  NEU: "Neutro",
}

export const FRAMING_LABELS: Record<string, string> = {
  crisis_conflicto: "Crisis / conflicto",
  logro_institucional: "Logro institucional",
  negligencia: "Negligencia",
  crecimiento: "Crecimiento",
  denuncia: "Denuncia",
  neutro_informativo: "Neutro informativo",
}

export const HEADLINE_LABELS: Record<string, string> = {
  informativo: "Informativo",
  alarmista: "Alarmista",
  sensacionalista: "Sensacionalista",
}

export const LEAD_LABELS: Record<string, string> = {
  social: "Social (ciudadanía)",
  oficialista: "Oficialista",
  tecnico: "Técnico (datos)",
}

export const SOURCE_LABELS: Record<string, string> = {
  citas_directas: "Citas directas",
  testimonios_anonimos: "Testimonios anónimos",
  datos_duros: "Datos duros",
  mixtas: "Mixtas",
  sin_fuentes: "Sin fuentes",
}

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  PERSON: "Persona",
  ORG: "Organización",
}

// Tono semántico de cada valor de encuadre (README §3 "Análisis de
// encuadre"): decide el color de la stat card en AnalysisCard.
export type Tone = "pos" | "neg" | "warn" | "neu"

const TONE: Record<string, Tone> = {
  // negativo
  crisis_conflicto: "neg",
  negligencia: "neg",
  denuncia: "neg",
  alarmista: "neg",
  sensacionalista: "neg",
  sin_fuentes: "neg",
  // positivo
  logro_institucional: "pos",
  crecimiento: "pos",
  informativo: "pos",
  tecnico: "pos",
  citas_directas: "pos",
  datos_duros: "pos",
  // advertencia
  oficialista: "warn",
  testimonios_anonimos: "warn",
  // neutro
  neutro_informativo: "neu",
  social: "neu",
  mixtas: "neu",
}

export function toneOf(value: string | null | undefined): Tone {
  if (!value) return "neu"
  return TONE[value] ?? "neu"
}

// Variables CSS del tono (ver docs/design_handoff_odin_redesign/README.md):
// texto en `--pos`/`--neg`/`--warn`/`--neu`, fondo en su variante `-soft`.
export function toneVars(tone: Tone): { color: string; bg: string; border: string } {
  return {
    color: `var(--${tone})`,
    bg: `var(--${tone}-soft)`,
    border: `var(--${tone})`,
  }
}
