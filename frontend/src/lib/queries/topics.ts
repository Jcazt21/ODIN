import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createTopic,
  deleteTopic,
  getTopicTree,
  listArticles,
  updateTopic,
  type TopicPayload,
  type TopicUpdatePayload,
} from "@/lib/odin-api"

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

export function useCreateTopic() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: TopicPayload) => createTopic(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: topicKeys.all })
    },
  })
}

export function useUpdateTopic() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: TopicUpdatePayload }) => updateTopic(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: topicKeys.all })
    },
  })
}

export function useDeleteTopic() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteTopic(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: topicKeys.all })
    },
  })
}
