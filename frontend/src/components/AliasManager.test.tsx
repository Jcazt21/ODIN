import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AliasManager } from "@/components/AliasManager"
import { DialogProvider } from "@/lib/dialog"
import * as odinApi from "@/lib/odin-api"
import type { EntityAlias } from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    listAliases: vi.fn(),
    createAlias: vi.fn(),
  }
})

const mockedListAliases = vi.mocked(odinApi.listAliases)
const mockedCreateAlias = vi.mocked(odinApi.createAlias)

const EXISTING: EntityAlias = {
  id: 1,
  alias: "MINERD",
  canonical_name: "Ministerio de Educación",
  type: "ORG",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}

function renderWithProviders() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <DialogProvider>
        <AliasManager />
      </DialogProvider>
    </QueryClientProvider>
  )
}

describe("AliasManager", () => {
  beforeEach(() => {
    mockedListAliases.mockReset()
    mockedCreateAlias.mockReset()
  })

  it("renders aliases loaded via React Query", async () => {
    mockedListAliases.mockResolvedValue([EXISTING])
    renderWithProviders()

    expect(await screen.findByText("MINERD")).toBeInTheDocument()
    expect(screen.getByText("Ministerio de Educación")).toBeInTheDocument()
    expect(mockedListAliases).toHaveBeenCalled()
  })

  it("shows the empty state when there are no aliases", async () => {
    mockedListAliases.mockResolvedValue([])
    renderWithProviders()

    expect(await screen.findByText("No hay siglas registradas aún.")).toBeInTheDocument()
  })

  it("creates a new alias and shows it in the list", async () => {
    const user = userEvent.setup()
    mockedListAliases.mockResolvedValue([EXISTING])
    const created: EntityAlias = {
      id: 2,
      alias: "MOPC",
      canonical_name: "Ministerio de Obras Públicas",
      type: "ORG",
      is_active: true,
      created_at: "2026-01-02T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    }
    mockedCreateAlias.mockResolvedValue(created)

    renderWithProviders()
    await screen.findByText("MINERD")

    await user.click(screen.getByRole("button", { name: /nueva sigla/i }))
    await user.type(screen.getByPlaceholderText("MINERD"), "MOPC")
    await user.type(
      screen.getByPlaceholderText("Ministerio de Educación de la República Dominicana"),
      "Ministerio de Obras Públicas"
    )

    mockedListAliases.mockResolvedValue([EXISTING, created])
    await user.click(screen.getByRole("button", { name: "Guardar" }))

    await waitFor(() => expect(mockedCreateAlias).toHaveBeenCalledWith(
      expect.objectContaining({ alias: "MOPC", canonical_name: "Ministerio de Obras Públicas" })
    ))
    expect(await screen.findByText("MOPC")).toBeInTheDocument()
  })
})
