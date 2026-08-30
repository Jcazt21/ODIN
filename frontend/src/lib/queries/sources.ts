import { useQuery } from "@tanstack/react-query"
import { listSources } from "@/lib/odin-api"

export const sourceKeys = {
  all: ["sources"] as const,
}

/** Los 9 medios del registro. Solo cambian cuando se agrega un scraper, o sea
 *  cuando se despliega código nuevo: no hay motivo para revalidarlos. */
export function useSources() {
  return useQuery({
    queryKey: sourceKeys.all,
    queryFn: listSources,
    staleTime: Infinity,
  })
}
