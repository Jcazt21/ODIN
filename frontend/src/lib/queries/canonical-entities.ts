import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query"
import {
  listCanonicalEntities,
  getCanonicalEntity,
  updateCanonicalEntity,
  mergeCanonicalEntities,
  type CanonicalEntityListParams,
  type CanonicalEntityUpdatePayload,
} from "@/lib/odin-api"

export const canonicalEntityKeys = {
  all: ["canonical-entities"] as const,
  lists: () => [...canonicalEntityKeys.all, "list"] as const,
  list: (params: CanonicalEntityListParams) => [...canonicalEntityKeys.lists(), params] as const,
  details: () => [...canonicalEntityKeys.all, "detail"] as const,
  detail: (id: number) => [...canonicalEntityKeys.details(), id] as const,
}

export function useCanonicalEntities(params: CanonicalEntityListParams) {
  return useQuery({
    queryKey: canonicalEntityKeys.list(params),
    queryFn: () => listCanonicalEntities(params),
    placeholderData: keepPreviousData,
  })
}

export function useCanonicalEntity(id: number | null, enabled: boolean) {
  return useQuery({
    queryKey: canonicalEntityKeys.detail(id ?? -1),
    queryFn: () => getCanonicalEntity(id as number),
    enabled: enabled && id != null,
  })
}

export function useUpdateCanonicalEntity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: CanonicalEntityUpdatePayload }) =>
      updateCanonicalEntity(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: canonicalEntityKeys.lists() })
    },
  })
}

export function useMergeCanonicalEntities() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ targetId, sourceId }: { targetId: number; sourceId: number }) =>
      mergeCanonicalEntities(targetId, sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: canonicalEntityKeys.lists() })
    },
  })
}
