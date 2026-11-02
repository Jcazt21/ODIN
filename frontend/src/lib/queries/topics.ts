import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { getTopicTree, listArticles } from "@/lib/odin-api"

export const ARTICLES_PAGE = 10

export const topicKeys = {
  all: ["topics"] as const,
  tree: (includeInactive: boolean) => [...topicKeys.all, "tree", includeInactive] as const,
  articles: (id: number, limit: number) => [...topicKeys.all, "articles", id, limit] as const,
}

export function useTopicTree(params: { include_inactive?: boolean } = {}) {
  const includeInactive = params.include_inactive ?? false
  return useQuery({
    queryKey: topicKeys.tree(includeInactive),
    queryFn: () => getTopicTree({ include_inactive: includeInactive }),
  })
}

/** Artículos de un tema (con su subárbol). No pide nada hasta `enabled`. */
export function useTopicArticles(id: number, enabled = false, limit = ARTICLES_PAGE) {
  return useQuery({
    queryKey: topicKeys.articles(id, limit),
    queryFn: () => listArticles({ topic_id: id, limit, sort: "published_at", order: "desc" }),
    enabled,
    placeholderData: keepPreviousData,
  })
}
