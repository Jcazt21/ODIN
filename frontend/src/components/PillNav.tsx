/**
 * PillNav — adaptado para Odin (sin react-router-dom).
 *
 * En lugar de href/Link, los items llevan un `tab` string.
 * Cuando el usuario hace click se llama `onTabChange(tab)`.
 * El texto "Odin" se muestra como wordmark en lugar de una imagen.
 */
import { useEffect, useRef, useState } from "react"
import { gsap } from "gsap"
import "./PillNav.css"

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
export interface PillNavItem {
  label: string
  tab: string
  ariaLabel?: string
}

interface PillNavProps {
  /** Texto del wordmark (por defecto "Odin") */
  wordmark?: string
  /** Items de navegación */
  items: PillNavItem[]
  /** Tab activo actualmente */
  activeTab: string
  /** Callback al cambiar de tab */
  onTabChange: (tab: string) => void
  className?: string
  ease?: string
  /** Color de fondo del contenedor pill */
  baseColor?: string
  /** Color de fondo de cada pill individual */
  pillColor?: string
  /** Color del texto al hacer hover */
  hoveredPillTextColor?: string
  /** Color del texto en los pills */
  pillTextColor?: string
  /** Animación de entrada al montar */
  initialLoadAnimation?: boolean
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────
export function PillNav({
  wordmark = "Odin",
  items,
  activeTab,
  onTabChange,
  className = "",
  ease = "power3.easeOut",
  baseColor = "oklch(0.19 0.016 285)",
  pillColor = "oklch(0.27 0.018 285)",
  hoveredPillTextColor = "oklch(0.96 0.005 285)",
  pillTextColor,
  initialLoadAnimation = true,
}: PillNavProps) {
  const resolvedPillTextColor = pillTextColor ?? "oklch(0.68 0.02 285)"

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const circleRefs = useRef<(HTMLSpanElement | null)[]>([])
  const tlRefs = useRef<gsap.core.Timeline[]>([])
  const activeTweenRefs = useRef<gsap.core.Tween[]>([])
  const hamburgerRef = useRef<HTMLButtonElement>(null)
  const mobileMenuRef = useRef<HTMLDivElement>(null)
  const navItemsRef = useRef<HTMLDivElement>(null)
  const logoRef = useRef<HTMLDivElement>(null)

  // ── layout & animations setup ────────────────────────────────────────────
  useEffect(() => {
    const layout = () => {
      circleRefs.current.forEach((circle, index) => {
        if (!circle?.parentElement) return

        const pill = circle.parentElement
        const rect = pill.getBoundingClientRect()
        const { width: w, height: h } = rect
        const R = ((w * w) / 4 + h * h) / (2 * h)
        const D = Math.ceil(2 * R) + 2
        const delta = Math.ceil(R - Math.sqrt(Math.max(0, R * R - (w * w) / 4))) + 1
        const originY = D - delta

        circle.style.width = `${D}px`
        circle.style.height = `${D}px`
        circle.style.bottom = `-${delta}px`

        gsap.set(circle, {
          xPercent: -50,
          scale: 0,
          transformOrigin: `50% ${originY}px`,
        })

        const label = pill.querySelector(".pill-label")
        const labelHover = pill.querySelector(".pill-label-hover")

        if (label) gsap.set(label, { y: 0 })
        if (labelHover) gsap.set(labelHover, { y: h + 12, opacity: 0 })

        tlRefs.current[index]?.kill()
        const tl = gsap.timeline({ paused: true })

        tl.to(circle, { scale: 1.2, xPercent: -50, duration: 2, ease, overwrite: "auto" }, 0)

        if (label) {
          tl.to(label, { y: -(h + 8), duration: 2, ease, overwrite: "auto" }, 0)
        }
        if (labelHover) {
          gsap.set(labelHover, { y: Math.ceil(h + 100), opacity: 0 })
          tl.to(labelHover, { y: 0, opacity: 1, duration: 2, ease, overwrite: "auto" }, 0)
        }

        tlRefs.current[index] = tl
      })
    }

    layout()
    window.addEventListener("resize", layout)
    document.fonts?.ready.then(layout).catch(() => {})

    // mobile menu initial state
    if (mobileMenuRef.current) {
      gsap.set(mobileMenuRef.current, { visibility: "hidden", opacity: 0 })
    }

    return () => window.removeEventListener("resize", layout)
  }, [items, ease, initialLoadAnimation])

  // ── entry animation: SOLO una vez al montar ──────────────────────────────
  // Va en su propio efecto con guard: si viviera en el efecto de layout (que
  // se re-ejecuta cuando cambia `items`), un re-render a mitad de la
  // animación relanzaría el gsap.from partiendo de width/opacity ~0 y la
  // barra quedaría invisible (pasaba al guardar un artículo).
  const didEntryAnimation = useRef(false)
  useEffect(() => {
    if (!initialLoadAnimation || didEntryAnimation.current) return
    didEntryAnimation.current = true
    if (logoRef.current) {
      gsap.from(logoRef.current, { scale: 0, duration: 0.5, ease })
    }
    if (navItemsRef.current) {
      gsap.from(navItemsRef.current, { width: 0, opacity: 0, duration: 0.5, ease, delay: 0.1 })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── hover handlers ───────────────────────────────────────────────────────
  function handleEnter(i: number) {
    const tl = tlRefs.current[i]
    if (!tl) return
    activeTweenRefs.current[i]?.kill()
    activeTweenRefs.current[i] = tl.tweenTo(tl.duration(), {
      duration: 0.3,
      ease,
      overwrite: "auto",
    }) as unknown as gsap.core.Tween
  }

  function handleLeave(i: number) {
    const tl = tlRefs.current[i]
    if (!tl) return
    activeTweenRefs.current[i]?.kill()
    activeTweenRefs.current[i] = tl.tweenTo(0, {
      duration: 0.2,
      ease,
      overwrite: "auto",
    }) as unknown as gsap.core.Tween
  }

  // ── mobile menu ──────────────────────────────────────────────────────────
  function toggleMobileMenu() {
    const next = !isMobileMenuOpen
    setIsMobileMenuOpen(next)

    const hamburger = hamburgerRef.current
    const menu = mobileMenuRef.current

    if (hamburger) {
      const lines = hamburger.querySelectorAll<HTMLSpanElement>(".hamburger-line")
      if (next) {
        gsap.to(lines[0], { rotation: 45, y: 3.5, duration: 0.3, ease })
        gsap.to(lines[1], { rotation: -45, y: -3.5, duration: 0.3, ease })
      } else {
        gsap.to(lines[0], { rotation: 0, y: 0, duration: 0.3, ease })
        gsap.to(lines[1], { rotation: 0, y: 0, duration: 0.3, ease })
      }
    }

    if (menu) {
      if (next) {
        gsap.set(menu, { visibility: "visible" })
        gsap.fromTo(
          menu,
          { opacity: 0, y: 8 },
          { opacity: 1, y: 0, duration: 0.25, ease }
        )
      } else {
        gsap.to(menu, {
          opacity: 0,
          y: 8,
          duration: 0.18,
          ease,
          onComplete: () => gsap.set(menu, { visibility: "hidden" }),
        })
      }
    }
  }

  // ── CSS vars ─────────────────────────────────────────────────────────────
  const cssVars = {
    "--base": baseColor,
    "--pill-bg": pillColor,
    "--hover-text": hoveredPillTextColor,
    "--pill-text": resolvedPillTextColor,
  } as React.CSSProperties

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="pill-nav-container">
      <nav
        className={`pill-nav ${className}`}
        aria-label="Navegación principal"
        style={cssVars}
      >
        {/* wordmark */}
        <div className="pill-logo" ref={logoRef} aria-hidden="true">
          <span className="pill-logo-text">{wordmark}</span>
        </div>

        {/* desktop nav */}
        <div className="pill-nav-items desktop-only" ref={navItemsRef}>
          <ul className="pill-list" role="menubar">
            {items.map((item, i) => (
              <li key={item.tab} role="none">
                <button
                  role="menuitem"
                  type="button"
                  id={`pillnav-${item.tab}`}
                  className={`pill${activeTab === item.tab ? " is-active" : ""}`}
                  aria-label={item.ariaLabel ?? item.label}
                  aria-current={activeTab === item.tab ? "page" : undefined}
                  onClick={() => onTabChange(item.tab)}
                  onMouseEnter={() => handleEnter(i)}
                  onMouseLeave={() => handleLeave(i)}
                >
                  <span
                    className="hover-circle"
                    aria-hidden="true"
                    ref={(el) => {
                      circleRefs.current[i] = el
                    }}
                  />
                  <span className="label-stack">
                    <span className="pill-label">{item.label}</span>
                    <span className="pill-label-hover" aria-hidden="true">
                      {item.label}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* mobile hamburger */}
        <button
          className="mobile-menu-button mobile-only"
          onClick={toggleMobileMenu}
          aria-label="Abrir menú"
          aria-expanded={isMobileMenuOpen}
          ref={hamburgerRef}
        >
          <span className="hamburger-line" />
          <span className="hamburger-line" />
        </button>
      </nav>

      {/* mobile popover */}
      <div
        className="mobile-menu-popover mobile-only"
        ref={mobileMenuRef}
        style={cssVars}
        role="menu"
      >
        <ul className="mobile-menu-list">
          {items.map((item) => (
            <li key={`mob-${item.tab}`} role="none">
              <button
                role="menuitem"
                type="button"
                className={`mobile-menu-link${activeTab === item.tab ? " is-active" : ""}`}
                onClick={() => {
                  onTabChange(item.tab)
                  setIsMobileMenuOpen(false)
                  if (mobileMenuRef.current) {
                    gsap.to(mobileMenuRef.current, {
                      opacity: 0,
                      y: 8,
                      duration: 0.18,
                      ease,
                      onComplete: () =>
                        gsap.set(mobileMenuRef.current!, { visibility: "hidden" }),
                    })
                  }
                  if (hamburgerRef.current) {
                    const lines =
                      hamburgerRef.current.querySelectorAll<HTMLSpanElement>(".hamburger-line")
                    gsap.to(lines[0], { rotation: 0, y: 0, duration: 0.3, ease })
                    gsap.to(lines[1], { rotation: 0, y: 0, duration: 0.3, ease })
                  }
                }}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
