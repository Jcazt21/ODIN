import { describe, expect, it } from "vitest"
import { formatDateShort, formatDateFull, isLowConfidence } from "@/lib/format"

describe("formatDateShort", () => {
  it("returns an em dash for null/undefined", () => {
    expect(formatDateShort(null)).toBe("—")
    expect(formatDateShort(undefined)).toBe("—")
  })

  it("returns the raw value for an unparseable date", () => {
    expect(formatDateShort("no-es-una-fecha")).toBe("no-es-una-fecha")
  })

  it("formats a valid ISO date as 'dd mon yy'", () => {
    expect(formatDateShort("2026-07-27T12:00:00Z")).toMatch(/^\d{2} [a-z]{3} \d{2}$/)
  })
})

describe("formatDateFull", () => {
  it("returns a fallback message for null/undefined", () => {
    expect(formatDateFull(null)).toBe("Fecha desconocida")
    expect(formatDateFull(undefined)).toBe("Fecha desconocida")
  })

  it("formats a valid date without throwing", () => {
    expect(formatDateFull("2026-07-27T12:00:00Z")).not.toBe("Fecha desconocida")
  })
})

describe("isLowConfidence", () => {
  it("is true below 0.9", () => {
    expect(isLowConfidence({ extraction_confidence: 0.5 })).toBe(true)
  })

  it("is false at or above 0.9", () => {
    expect(isLowConfidence({ extraction_confidence: 0.9 })).toBe(false)
    expect(isLowConfidence({ extraction_confidence: 1 })).toBe(false)
  })

  it("is false when confidence is missing", () => {
    expect(isLowConfidence({})).toBe(false)
    expect(isLowConfidence({ extraction_confidence: null })).toBe(false)
  })
})
