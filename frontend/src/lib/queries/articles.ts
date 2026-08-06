import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query"
import {
  listArticles,
  getArticle,
  getArticleFilterOptions,
  updateArticle,
  deleteArticle,
  analyzeUrl,
  saveArticle,
  type ArticleListParams,
  type ArticleUpdatePayload,
  type SaveArticlePayload,
  type JobStatus,
  type AnalyzeStage,
} from "@/lib/odin-api"

export const articleKeys = {
  all: ["articles"] as const,
  lists: () => [...articleKeys.all, "list"] as const,
  list: (params: ArticleListParams) => [...articleKeys.lists(), params] as const,
  details: () => [...articleKeys.all, "detail"] as const,
  detail: (id: number) => [...articleKeys.details(), id] as const,
  filters: () => [...articleKeys.all, "filters"] as const,
}

export function useArticles(params: ArticleListParams) {
  return useQuery({
    queryKey: articleKeys.list(params),
    queryFn: () => listArticles(params),
    placeholderData: keepPreviousData,
  })
}

export function useArticle(id: number | null) {
  return useQuery({
    queryKey: articleKeys.detail(id ?? -1),
    queryFn: () => getArticle(id as number),
    enabled: id != null,
  })
}

export function useArticleFilterOptions() {
  return useQuery({
    queryKey: articleKeys.filters(),
    queryFn: getArticleFilterOptions,
    staleTime: 5 * 60_000,
  })
}

export function useUpdateArticle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ArticleUpdatePayload }) =>
      updateArticle(id, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(articleKeys.detail(updated.id as number), updated)
      queryClient.invalidateQueries({ queryKey: articleKeys.lists() })
    },
  })
}

export function useDeleteArticle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteArticle(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: articleKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: articleKeys.lists() })
    },
  })
}

/** Analizar una URL nueva es una escritura con efecto secundario caro (fetch +
 *  NLP, hasta ~60s vía polling de job): mutation, no query, para que nunca se
 *  dispare sola por un refetch/StrictMode y quede modelada con su propio
 *  estado de carga/error igual que el resto de las escrituras. */
export function useAnalyzeUrl(onStatus?: (status: JobStatus, stage: AnalyzeStage | null) => void) {
  return useMutation({
    mutationFn: (url: string) => analyzeUrl(url, onStatus),
  })
}

export function useSaveArticle() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SaveArticlePayload) => saveArticle(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: articleKeys.lists() })
    },
  })
}
