import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  listAliases,
  createAlias,
  updateAlias,
  deleteAlias,
  toggleAlias,
  type AliasPayload,
  type AliasUpdatePayload,
  type EntityAlias,
} from "@/lib/odin-api"

export const aliasKeys = {
  all: ["aliases"] as const,
  list: (q?: string) => [...aliasKeys.all, "list", q ?? ""] as const,
}

export function useAliases(q?: string) {
  return useQuery({
    queryKey: aliasKeys.list(q),
    queryFn: () => listAliases(q),
  })
}

export function useCreateAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: AliasPayload) => createAlias(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aliasKeys.all })
    },
  })
}

export function useUpdateAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AliasUpdatePayload }) => updateAlias(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aliasKeys.all })
    },
  })
}

export function useDeleteAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAlias(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aliasKeys.all })
    },
  })
}

export function useToggleAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (alias: EntityAlias) => toggleAlias(alias),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aliasKeys.all })
    },
  })
}
