import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AnalyzeProgress } from "./AnalyzeProgress"
import type { JobStep } from "@/lib/odin-api"

const step = (key: string, status: string, extra: Partial<JobStep> = {}): JobStep => ({
  key,
  status,
  detail: null,
  started_ms: 0,
  duration_ms: status === "running" ? null : 1200,
  ...extra,
})

describe("AnalyzeProgress", () => {
  it("dibuja las tres ramas desde el primer segundo", () => {
    render(<AnalyzeProgress jobStatus="pending" steps={[]} startedAt={Date.now()} />)
    for (const name of ["descarga", "análisis", "consolidación"]) {
      expect(screen.getByText(name)).toBeInTheDocument()
    }
    expect(screen.getByRole("status")).toHaveTextContent("Encolando")
  })

  it("anuncia el paso en curso y muestra detalle y duración de los hechos", () => {
    render(
      <AnalyzeProgress
        jobStatus="running"
        startedAt={Date.now()}
        steps={[step("fetch", "done", { detail: "84 KB" }), step("extract", "running")]}
      />
    )
    expect(screen.getByRole("status")).toHaveTextContent("Extraer el artículo")
    expect(screen.getByText("84 KB")).toBeInTheDocument()
    expect(screen.getByText("1.2 s")).toBeInTheDocument()
  })

  it("marca como omitido el paso que no hizo falta", () => {
    render(
      <AnalyzeProgress
        jobStatus="running"
        startedAt={Date.now()}
        steps={[
          step("fetch", "done"),
          step("extract", "done"),
          step("analyze", "done"),
          step("canonicalize", "running"),
        ]}
      />
    )
    expect(screen.getByText("no hizo falta")).toBeInTheDocument()
  })
})
