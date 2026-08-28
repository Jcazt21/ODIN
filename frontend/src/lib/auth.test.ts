import { describe, expect, it, beforeEach } from "vitest"
import { clearSession, getToken, setSession } from "@/lib/auth"
import { queryClient } from "@/lib/query-client"

describe("clearSession", () => {
  beforeEach(() => {
    queryClient.clear()
    localStorage.clear()
  })

  it("borra el token y la identidad", () => {
    setSession("un-token", "jazar")

    clearSession()

    // Por la API pública: la clave interna es un detalle de implementación.
    expect(getToken()).toBeNull()
  })

  it("vacía la caché de datos del usuario que se va", () => {
    /* Sin esto, quien entra después hereda en memoria los reportes, el listado
       de usuarios y el KPI del anterior: no hay recarga de página que los
       tire, porque es una SPA. */
    setSession("un-token", "jazar")
    queryClient.setQueryData(["articles", "list", {}], [{ id: 1, title: "Reporte ajeno" }])
    queryClient.setQueryData(["documentalists", "list"], [{ id: 1, username: "jazar" }])

    clearSession()

    expect(queryClient.getQueryData(["articles", "list", {}])).toBeUndefined()
    expect(queryClient.getQueryData(["documentalists", "list"])).toBeUndefined()
  })
})
