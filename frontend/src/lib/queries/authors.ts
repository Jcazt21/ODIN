import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { listArticles, listAuthors, type AuthorListParams } from "@/lib/odin-api"

export const ARTICLES_PAGE = 10

export const authorKeys = {
  all: ["authors"] as const,
  list: (params: AuthorListParams) => [...authorKeys.all, "list", params] as const,
  articles: (name: string, limit: number) => [...authorKeys.all, "articles", name, limit] as const,
}

export function useAuthors(params: AuthorListParams) {
  return useQuery({
    queryKey: authorKeys.list(params),
    queryFn: () => listAuthors(params),
    placeholderData: keepPreviousData,
  })
}

/** Artículos de un autor. No pide nada hasta `enabled` (fila expandida). */
export function useAuthorArticles(name: string, enabled = false, limit = ARTICLES_PAGE) {
  return useQuery({
    queryKey: authorKeys.articles(name, limit),
    queryFn: () => listArticles({ author: name, limit, sort: "published_at", order: "desc" }),
    enabled,
    placeholderData: keepPreviousData,
  })
}
