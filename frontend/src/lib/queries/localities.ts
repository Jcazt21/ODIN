import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getLocalityTree,
  getArticleLocalities,
  addArticleLocality,
  replaceArticleLocalities,
  deleteArticleLocality,
  type ArticleLocalityPayload,
} from "@/lib/odin-api"

export const localityKeys = {
  all: ["localities"] as const,
  tree: () => [...localityKeys.all, "tree"] as const,
  forArticle: (articleId: number) => [...localityKeys.all, "article", articleId] as const,
}

/** El árbol completo son ~204 nodos y solo cambia cuando el Congreso crea un
 *  municipio, así que se cachea sin vencimiento: el selector abre al instante
 *  y no se pide de nuevo en cada montaje. */
export function useLocalityTree() {
  return useQuery({
    queryKey: localityKeys.tree(),
    queryFn: getLocalityTree,
    staleTime: Infinity,
  })
}

export function useArticleLocalities(articleId: number | undefined) {
  return useQuery({
    queryKey: localityKeys.forArticle(articleId ?? 0),
    queryFn: () => getArticleLocalities(articleId as number),
    enabled: articleId !== undefined,
  })
}

export function useAddArticleLocality(articleId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ArticleLocalityPayload) => addArticleLocality(articleId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: localityKeys.forArticle(articleId) })
    },
  })
}

export function useReplaceArticleLocalities(articleId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ArticleLocalityPayload[]) =>
      replaceArticleLocalities(articleId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: localityKeys.forArticle(articleId) })
    },
  })
}

export function useDeleteArticleLocality(articleId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (linkId: number) => deleteArticleLocality(articleId, linkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: localityKeys.forArticle(articleId) })
    },
  })
}
