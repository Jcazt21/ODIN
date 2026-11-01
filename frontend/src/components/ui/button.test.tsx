import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { Button } from "./button"

it("da feedback de press con scale y no anima todo", () => {
  render(<Button>Guardar</Button>)
  const cls = screen.getByRole("button", { name: "Guardar" }).className
  expect(cls).toContain("active:scale-[0.97]")
  expect(cls).toContain("transition-[color,background-color,transform]")
  expect(cls).not.toContain("transition-all")
})
