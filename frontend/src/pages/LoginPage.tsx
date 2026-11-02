import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { LoginScreen } from "@/components/LoginScreen"

interface LoginPageProps {
  authed: boolean
  onSuccess: (username: string) => void
}

export function LoginPage({ authed, onSuccess }: LoginPageProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? "/analyze"

  if (authed) return <Navigate to={from} replace />

  return (
    <LoginScreen
      onSuccess={(username) => {
        onSuccess(username)
        navigate(from, { replace: true })
      }}
    />
  )
}
