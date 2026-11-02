import { sourceLogo } from "@/lib/source-logos"
import { cn } from "@/lib/utils"

/** Ícono del medio junto a su nombre. Decorativo (`alt=""`): el nombre ya está
 *  al lado en texto, y repetirlo en el alt haría que un lector de pantalla lo
 *  diga dos veces. Sin ícono para ese slug, no renderiza nada.
 */
export function SourceLogo({ source, className }: { source: string; className?: string }) {
  const src = sourceLogo(source)
  if (!src) return null
  return (
    <img
      src={src}
      alt=""
      width={16}
      height={16}
      loading="lazy"
      className={cn("inline-block size-4 shrink-0 rounded-sm object-contain", className)}
    />
  )
}
