import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { Button } from "@/components/ui/button"

interface ConfirmOptions {
  title: string
  body: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}

interface PendingDialog extends ConfirmOptions {
  resolve: (value: boolean) => void
}

const DialogContext = createContext<((opts: ConfirmOptions) => Promise<boolean>) | null>(null)

export function DialogProvider({ children }: { children: ReactNode }) {
  const [dialog, setDialog] = useState<PendingDialog | null>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  const confirm = useCallback((opts: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setDialog({ ...opts, resolve })
    })
  }, [])

  const close = useCallback(
    (value: boolean) => {
      dialog?.resolve(value)
      setDialog(null)
    },
    [dialog]
  )

  useEffect(() => {
    if (!dialog) return
    cancelRef.current?.focus()

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault()
        close(false)
        return
      }
      if (e.key !== "Tab") return
      const panel = panelRef.current
      if (!panel) return
      const focusable = panel.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [dialog, close])

  return (
    <DialogContext.Provider value={confirm}>
      {children}
      {dialog && (
        <div
          className="fixed inset-0 z-[100] grid place-items-center p-6"
          style={{
            background: "oklch(0.2 0.02 265 / 0.5)",
            backdropFilter: "blur(2px)",
            WebkitBackdropFilter: "blur(2px)",
          }}
          onClick={() => close(false)}
        >
          <div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="odin-dialog-title"
            className="w-full max-w-[400px] rounded-xl border p-[22px]"
            style={{
              background: "var(--panel-strong)",
              backdropFilter: "blur(14px)",
              WebkitBackdropFilter: "blur(14px)",
              borderColor: "var(--border)",
              boxShadow: "var(--shadow)",
              animation: "odinIn 0.16s ease",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="odin-dialog-title" className="text-[15.5px] font-semibold">
              {dialog.title}
            </h2>
            <div className="mt-2 text-[13px] leading-[1.6]" style={{ color: "var(--muted-foreground)" }}>
              {dialog.body}
            </div>
            <div className="mt-5 flex justify-end gap-[9px]">
              <Button ref={cancelRef} type="button" variant="outline" onClick={() => close(false)}>
                {dialog.cancelLabel ?? "Cancelar"}
              </Button>
              <Button
                type="button"
                variant={dialog.danger ? "destructive" : "default"}
                onClick={() => close(true)}
              >
                {dialog.confirmLabel ?? "Confirmar"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  )
}

/** `const confirm = useConfirm(); if (await confirm({...})) { ... }` */
export function useConfirm() {
  const ctx = useContext(DialogContext)
  if (!ctx) throw new Error("useConfirm() debe usarse dentro de <DialogProvider>")
  return ctx
}
