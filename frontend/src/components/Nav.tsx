import { Moon, Sun } from "lucide-react"
import { LogoutLinear } from "mx-icons"
import { cn } from "@/lib/utils"
import { useConfirm } from "@/lib/dialog"

export interface NavItem {
  label: string
  tab: string
  count?: number
}

interface NavProps {
  items: NavItem[]
  activeTab: string
  onTabChange: (tab: string) => void
  username: string | null
  onLogout: () => void
  theme: "light" | "dark"
  onToggleTheme: () => void
}

/** Nav pill sticky (README §2 "Workspace — shell y navegación"). Reemplaza PillNav. */
export function Nav({ items, activeTab, onTabChange, username, onLogout, theme, onToggleTheme }: NavProps) {
  const confirm = useConfirm()

  async function handleLogout() {
    const ok = await confirm({
      title: "¿Cerrar sesión?",
      body: "Se descartará cualquier análisis en vista previa que no haya guardado.",
      confirmLabel: "Cerrar sesión",
      danger: true,
    })
    if (ok) onLogout()
  }

  return (
    <nav
      className="sticky top-4 z-40 mx-auto flex w-fit max-w-full items-center gap-3.5 rounded-full border py-[7px] pr-[7px] pl-[18px] backdrop-blur-[12px]"
      style={{
        background: "var(--panel-strong)",
        borderColor: "var(--border)",
        boxShadow: "var(--shadow)",
      }}
    >
      <span className="flex items-center gap-1.5 pr-1.5">
        <span className="text-[14px] font-semibold" style={{ letterSpacing: "0.16em" }}>
          ODIN
        </span>
        <span
          className="rounded-full px-[6px] py-[1px] font-mono text-[9px] font-medium uppercase"
          style={{ background: "var(--surface-2)", color: "var(--faint)", letterSpacing: "0.04em" }}
        >
          beta v2.1.1
        </span>
      </span>

      <div className="flex flex-1 gap-0.5">
        {items.map((item) => {
          const active = item.tab === activeTab
          return (
            <button
              key={item.tab}
              type="button"
              onClick={() => onTabChange(item.tab)}
              className={cn(
                "inline-flex items-center gap-[7px] rounded-full px-[15px] py-[7px] text-[13px] transition-colors",
                active ? "font-semibold" : "font-medium"
              )}
              style={{
                background: active ? "var(--primary)" : "transparent",
                color: active ? "var(--accent-fg)" : "var(--muted-foreground)",
              }}
            >
              {item.label}
              {typeof item.count === "number" && (
                <span
                  className="font-mono text-[10.5px]"
                  style={{ color: active ? "var(--accent-fg)" : "var(--faint)" }}
                >
                  {item.count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <button
        type="button"
        onClick={onToggleTheme}
        aria-label={theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
        className="inline-flex size-[30px] items-center justify-center rounded-full border transition-colors hover:text-foreground"
        style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--faint)" }}
      >
        {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </button>

      {username && (
        <span className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>
          {username}
        </span>
      )}

      <button
        type="button"
        onClick={handleLogout}
        aria-label="Cerrar sesión"
        title="Cerrar sesión"
        className="inline-flex size-[30px] items-center justify-center rounded-full border transition-colors hover:text-[var(--neg)] hover:border-[var(--neg)]"
        style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--faint)" }}
      >
        <LogoutLinear size={16} color="currentColor" />
      </button>
    </nav>
  )
}
