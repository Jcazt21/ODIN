# Design Handoff — Odin

Este directorio contiene el paquete de traspaso para rediseñar la interfaz de
Odin. Está pensado para dárselo a un agente/equipo de diseño (p. ej. Claude
Design) que no conoce el proyecto y tiene que producir una interfaz seria a
partir de lo que existe hoy.

## Qué hay aquí

- **[DESIGN_HANDOFF.md](./DESIGN_HANDOFF.md)** — el documento principal.
  Inventario completo de pantallas, componentes, estados, flujo de
  navegación, modelo de datos que llega del backend, tokens visuales
  actuales y qué está fijo vs. qué se puede rediseñar libremente.

## Qué es Odin, en una frase

Una herramienta interna (un solo operador, sin registro público) para
analizar artículos de prensa dominicana: pega una URL, el backend la
analiza con IA (sentimiento, encuadre, figuras/empresas mencionadas), el
operador revisa y corrige el resultado, y lo guarda como reporte
consultable con filtros.

## Cómo ver la interfaz actual funcionando

No se generaron capturas de pantalla como parte de este handoff (esta sesión
no tenía herramienta de navegador/captura disponible). La forma más fiel de
ver el estado actual es correr la app localmente:

```bash
# Terminal 1 — backend (desde la raíz del repo)
.venv/bin/python main.py          # o: docker-compose up

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

Necesita un usuario válido (`ODIN_USER`/`ODIN_PASSWORD` o equivalente en
`.env`) para pasar del login al workspace. Si se quiere solo mirar el
lenguaje visual sin backend corriendo, la pantalla de login y el fondo
animado (Aurora) ya se ven sin autenticarse.

## Alcance del rediseño

El objetivo es una interfaz "seria" — la actual es funcional (construida
rápido con shadcn + componentes sueltos de "React Bits"/hover-button/
shimmer-text) pero no tiene una dirección de diseño intencional. El
[DESIGN_HANDOFF.md](./DESIGN_HANDOFF.md) marca explícitamente qué contrato
de datos y de comportamiento hay que respetar, y qué es enteramente
rediseñable (layout, tipografía, color, navegación, componentes,
animaciones).
