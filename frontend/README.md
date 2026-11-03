# Odin — frontend

React 19 + TypeScript + Vite, Tailwind 4, TanStack Query. Consume la API de FastAPI del backend.

```bash
npm ci
npm run dev       # servidor de desarrollo
npm run lint      # oxlint
npm test          # vitest
npm run build     # tsc -b + vite build
npm run generate:types   # regenera src/lib/api-types.ts desde el OpenAPI del backend
```

Node 22 (`../.nvmrc`). Los tipos de la API (`src/lib/api-types.ts`) están versionados:
regenéralos cuando cambien endpoints o schemas del backend.
