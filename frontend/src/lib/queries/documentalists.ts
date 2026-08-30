import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  listDocumentalists,
  getDocumentalistKpi,
  createDocumentalist,
  resetDocumentalistPin,
  updateDocumentalist,
  exportArticles,
  type DocumentalistPayload,
  type DocumentalistUpdatePayload,
} from "@/lib/odin-api"

export const documentalistKeys = {
  all: ["documentalists"] as const,
  list: () => [...documentalistKeys.all, "list"] as const,
  kpi: (from?: string, to?: string) => [...documentalistKeys.all, "kpi", from ?? "", to ?? ""] as const,
}

export function useDocumentalists() {
  return useQuery({ queryKey: documentalistKeys.list(), queryFn: listDocumentalists })
}

/** Solo lo consume la pantalla de admin: el backend responde 403 al resto. */
export function useDocumentalistKpi(dateFrom?: string, dateTo?: string, enabled = true) {
  return useQuery({
    queryKey: documentalistKeys.kpi(dateFrom, dateTo),
    queryFn: () => getDocumentalistKpi({ date_from: dateFrom, date_to: dateTo }),
    enabled,
  })
}

export function useCreateDocumentalist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: DocumentalistPayload) => createDocumentalist(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentalistKeys.all }),
  })
}

export function useResetDocumentalistPin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => resetDocumentalistPin(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentalistKeys.all }),
  })
}

export function useUpdateDocumentalist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: DocumentalistUpdatePayload }) =>
      updateDocumentalist(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentalistKeys.all }),
  })
}

export function useExportArticles() {
  return useMutation({ mutationFn: (ids: number[]) => exportArticles(ids) })
}
