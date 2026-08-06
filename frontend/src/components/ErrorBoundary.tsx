import { Component, type ErrorInfo, type ReactNode } from "react"
import { RefreshCcw, TriangleAlert } from "lucide-react"

interface Props {
  children: ReactNode
  /** Se reinicia el boundary si esta clave cambia (p. ej. la ruta): así un
   *  error en /reportes no deja el resto de la app permanentemente rota tras
   *  navegar a /analizar. */
  resetKey?: unknown
}

interface State {
  error: Error | null
  resetKey: unknown
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetKey: this.props.resetKey }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  // Si `resetKey` cambió desde el último render (p. ej. la ruta), se limpia
  // el error acá en vez de en componentDidUpdate: evita el ciclo extra de
  // render que dispara un setState fuera de este método.
  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey !== state.resetKey) {
      return { error: null, resetKey: props.resetKey }
    }
    return null
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div
          role="alert"
          className="flex w-full flex-col items-center gap-3 rounded-xl border p-10 text-center"
          style={{ background: "var(--panel)", borderColor: "var(--border)" }}
        >
          <TriangleAlert className="size-8" style={{ color: "var(--neg)" }} />
          <p className="text-[15px] font-semibold">Algo salió mal en esta vista</p>
          <p className="max-w-[48ch] text-[13px]" style={{ color: "var(--muted-foreground)" }}>
            {this.state.error.message || "Ocurrió un error inesperado."}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-1 inline-flex items-center gap-1.5 rounded-lg border px-3.5 py-2 text-[13px]"
            style={{ borderColor: "var(--border)" }}
          >
            <RefreshCcw className="size-3.5" />
            Reintentar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
