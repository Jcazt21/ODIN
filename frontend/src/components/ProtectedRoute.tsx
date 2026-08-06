import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"

export function ProtectedRoute({ authed, children }: { authed: boolean; children: ReactNode }) {
  if (!authed) return <Navigate to="/login" replace />
  return children
}
