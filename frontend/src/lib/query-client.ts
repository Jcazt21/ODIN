import { QueryClient } from "@tanstack/react-query"
import { OdinApiError } from "@/lib/api-error"

// No reintentar en errores de la API de Odin (4xx conocidos: sesión vencida,
// validación, "no encontrado"): reintentar solo tiene sentido para fallos de
// red transitorios, que llegan como TypeError de fetch, no como OdinApiError.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof OdinApiError) return false
        return failureCount < 2
      },
      staleTime: 15_000,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
})
