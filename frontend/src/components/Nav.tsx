import { Menu } from "@base-ui/react/menu"
import {
  Building2,
  PenLine,
  Shapes,
  ChevronsUpDown,
  FileText,
  Menu as MenuIcon,
  ScanSearch,
  Settings,
  Tags,
  Users,
  type LucideIcon,
} from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useConfirm } from "@/lib/dialog"
import type { Theme } from "@/lib/theme"

interface NavProps {
  username: string | null
  role?: string | null
  theme: Theme
  onToggleTheme: () => void
  onLogout: () => void
}

interface NavItem {
  label: string
  to: string
  icon: LucideIcon
}

const GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Principal",
    items: [
      { label: "Analizar", to: "/analyze", icon: ScanSearch },
      { label: "Reportes", to: "/reports", icon: FileText },
    ],
  },
  {
    label: "Administración",
    items: [
      { label: "Entidades", to: "/entities", icon: Building2 },
      { label: "Siglas", to: "/aliases", icon: Tags },
      { label: "Autores", to: "/authors", icon: PenLine },
      { label: "Temas", to: "/topics", icon: Shapes },
      { label: "Documentalistas", to: "/documentalists", icon: Users },
    ],
  },
  { label: "Cuenta", items: [{ label: "Ajustes", to: "/settings", icon: Settings }] },
]

const ROLE_LABELS: Record<string, string> = { admin: "Administrador", documentalista: "Documentalista" }

const menuItemClass =
  "flex h-9 cursor-default items-center rounded-lg px-3 text-sm outline-none select-none data-[highlighted]:bg-muted"

/** Sidebar fijo en escritorio; en pantallas angostas, barra superior con un cajón. */
export function Nav({ username, role, theme, onToggleTheme, onLogout }: NavProps) {
  const confirm = useConfirm()
  const popupRef = useRef<HTMLDivElement>(null)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const idBase = useId()
  const [open, setOpen] = useState(false)

  function closeDrawer() {
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return
      setOpen(false)
      toggleRef.current?.focus()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [open])

  // Base UI enfoca el popup al abrir con el mouse; el primer ítem es lo esperable en ambos casos.
  function focusFirstItem(isOpen: boolean) {
    if (isOpen) setTimeout(() => popupRef.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus(), 0)
  }

  async function handleLogout() {
    const ok = await confirm({
      title: "¿Cerrar sesión?",
      body: "Se descartará cualquier análisis en vista previa que no haya guardado.",
      confirmLabel: "Cerrar sesión",
      danger: true,
    })
    if (ok) onLogout()
  }

  const name = username ?? "Cuenta"

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 bg-[image:var(--shell-gradient)] px-4 text-[var(--sidebar-foreground)] lg:hidden">
        <button
          ref={toggleRef}
          type="button"
          aria-label={open ? "Cerrar menú" : "Abrir menú"}
          aria-expanded={open}
          aria-controls={`${idBase}-sidebar`}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex size-9 items-center justify-center rounded-lg transition-[background-color,transform] duration-150 ease-out outline-none hover:bg-white/10 focus-visible:ring-3 focus-visible:ring-white/60 active:scale-[0.97]"
        >
          <MenuIcon aria-hidden className="size-5" />
        </button>
        <span className="text-base font-semibold tracking-tight">Odin</span>
      </header>

      <div
        data-testid="nav-backdrop"
        aria-hidden
        onClick={closeDrawer}
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity duration-200 ease-[var(--ease-out)] lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
      />

      <aside
        id={`${idBase}-sidebar`}
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-[image:var(--shell-gradient)] text-[var(--sidebar-foreground)] transition-[transform,visibility] duration-200 ease-[var(--ease-out)]",
          "lg:static lg:z-auto lg:h-full lg:w-auto lg:translate-x-0 lg:visible lg:bg-none",
          open ? "translate-x-0 visible" : "max-lg:-translate-x-full max-lg:invisible"
        )}
      >
        <Link to="/analyze" onClick={closeDrawer} className="px-6 pt-6 pb-5 text-xl font-semibold tracking-tight text-white outline-none focus-visible:underline">
          Odin
        </Link>

        <nav aria-label="Navegación principal" className="flex-1 space-y-6 overflow-y-auto px-4 pb-6">
          {GROUPS.map((group) => (
            <div key={group.label} role="group" aria-labelledby={`${idBase}-${group.label}`}>
              <p id={`${idBase}-${group.label}`} className="px-3 pb-2 text-xs font-medium tracking-wide text-white/60">
                {group.label}
              </p>
              <ul className="space-y-1">
                {group.items.map(({ label, to, icon: Icon }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      onClick={closeDrawer}
                      className={({ isActive }) =>
                        cn(
                          "group/link flex h-11 items-center gap-3 rounded-xl px-3 text-[15px] transition-colors duration-150 ease-out outline-none focus-visible:ring-3 focus-visible:ring-white/60",
                          isActive
                            ? "bg-[var(--sidebar-accent)] font-medium text-[var(--sidebar-accent-foreground)]"
                            : "text-[var(--sidebar-foreground)]/85 hover:bg-white/10 hover:text-[var(--sidebar-foreground)]"
                        )
                      }
                    >
                      <>
                        <Icon aria-hidden className="size-5 shrink-0" />
                        {label}
                      </>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="shrink-0 border-t border-[var(--sidebar-border)] px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <Menu.Root onOpenChange={focusFirstItem}>
            <Menu.Trigger className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-[15px] text-[var(--sidebar-foreground)] transition-[background-color,transform] duration-150 ease-out outline-none hover:bg-white/10 data-[popup-open]:bg-white/10 focus-visible:ring-3 focus-visible:ring-white/60 active:scale-[0.97]">
              <span
                aria-hidden
                className="grid size-8 shrink-0 place-items-center rounded-full bg-[var(--accent-soft)] text-sm font-medium text-primary uppercase"
              >
                {name.charAt(0)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium leading-tight">{name}</span>
                <span className="block truncate text-xs leading-tight text-white/60">{(role && ROLE_LABELS[role]) || "Documentalista"}</span>
              </span>
              <ChevronsUpDown aria-hidden className="size-4 shrink-0 text-white/60" />
            </Menu.Trigger>
            <Menu.Portal>
              <Menu.Positioner side="top" align="start" sideOffset={8} className="z-[60]">
                <Menu.Popup
                  ref={popupRef}
                  className="min-w-[var(--anchor-width)] origin-[var(--transform-origin)] rounded-lg border bg-popover p-1 text-popover-foreground shadow-[var(--shadow)] transition-[opacity,transform] duration-150 ease-out outline-none data-[ending-style]:scale-[0.97] data-[ending-style]:opacity-0 data-[starting-style]:scale-[0.97] data-[starting-style]:opacity-0"
                >
                  <Menu.Item className={menuItemClass} onClick={onToggleTheme}>
                    {theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
                  </Menu.Item>
                  <Menu.Item className={cn(menuItemClass, "text-destructive")} onClick={handleLogout}>
                    Cerrar sesión
                  </Menu.Item>
                </Menu.Popup>
              </Menu.Positioner>
            </Menu.Portal>
          </Menu.Root>
        </div>
      </aside>
    </>
  )
}
