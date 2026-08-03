# Plan de deploy gratis (para pruebas con el cliente)

Objetivo: que el cliente pueda probar Odin en un ambiente accesible por URL,
sin costo, aceptando cold starts y límites de plan free. No es para
producción con tráfico real.

## Resumen de piezas

| Componente | Servicio recomendado | Por qué |
|---|---|---|
| Frontend (React/Vite) | Vercel o Cloudflare Pages | Deploy estático directo desde git, plan free generoso |
| Backend (FastAPI + spaCy + pysentimiento) | Google Cloud Run | Free tier permite más RAM que alternativas típicas; escala a cero cuando no hay tráfico |
| Base de datos (Postgres) | Neon o Supabase | Postgres serverless, plan free razonable, compatible con `DATABASE_URL` actual |
| Scraper (`main.py`) | GitHub Actions (cron) o Cloud Run Jobs + Cloud Scheduler | No necesita correr 24/7; se dispara periódicamente |

---

## 1. Frontend — Vercel / Cloudflare Pages

- Repo: `frontend/` (Vite + React + Tailwind).
- Build command: `npm run build` (ya definido en `package.json`).
- Output dir: `dist/`.
- Variable de entorno: URL del backend en Cloud Run (ej. `VITE_API_URL`).
- Ambas opciones tienen plan free sin tarjeta, deploy automático en cada
  push, y HTTPS gratis.

**Elegir Vercel** si se prefiere DX más simple y previews por PR.
**Elegir Cloudflare Pages** si se quiere evitar cualquier límite de build
minutes/bandwidth a futuro (Cloudflare es más generoso en ese punto).

---

## 2. Backend — Google Cloud Run

Por qué no Render/Railway free:
- Render free tier: 512MB RAM — insuficiente para tener spaCy `es_core_news_lg`
  + pysentimiento (BETO/RoBERTuito) cargados a la vez sin OOM.
- Railway ya no ofrece tier gratuito permanente (solo crédito de prueba).

Cloud Run free tier (siempre gratis, sin expirar):
- ~2 millones de requests/mes incluidos.
- Escala a cero: si no hay tráfico, no se cobra cómputo.
- Permite configurar más memoria (1–4GB) dentro de la cuota gratuita si el
  uso se mantiene bajo.

### Pasos

1. `Dockerfile.backend` ya sirve tal cual (usa `uvicorn api:app`, expone 8000).
2. Instalar `gcloud` CLI y autenticar (`gcloud auth login`).
3. Build y push de la imagen:
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/odin-backend -f Dockerfile.backend .
   ```
4. Deploy:
   ```bash
   gcloud run deploy odin-backend \
     --image gcr.io/PROJECT_ID/odin-backend \
     --platform managed \
     --region us-central1 \
     --memory 2Gi \
     --cpu 2 \
     --allow-unauthenticated \
     --set-env-vars DATABASE_URL=<url-de-neon-o-supabase> \
     --set-env-vars GEMINI_API_KEY=<opcional, solo si el cliente probará ese analyzer>
   ```
5. Nota sobre cold start: la primera petición tras un período idle tarda
   varios segundos (carga de modelos NLP en memoria). Aceptable para demo,
   comunicarlo al cliente.
6. El caché de HuggingFace (`hf_cache` en docker-compose) no persiste entre
   instancias de Cloud Run — cada cold start puede re-descargar pesos si no
   están ya en la imagen. Revisar si `pysentimiento` descarga en runtime o
   si conviene bakearlo en el Dockerfile (capa dedicada, igual que se hizo
   con el modelo de spaCy) para evitar ese costo en cada arranque.

---

## 3. Base de datos — Neon o Supabase (Postgres free)

- Crear proyecto en [neon.tech](https://neon.tech) o [supabase.com](https://supabase.com).
- Copiar el connection string y usarlo como `DATABASE_URL` en el backend
  (formato ya compatible: `postgresql+psycopg2://...`).
- Neon: se "duerme" tras inactividad (similar a Cloud Run, cold start
  aceptable para demo). Free tier: 0.5GB storage.
- Supabase: free tier con proyecto pausado tras 1 semana sin uso (hay que
  reactivarlo manualmente) — considerar si la demo puede tener huecos largos
  de inactividad.

**Elegir Neon** si se espera actividad esporádica sin intervención manual.
**Elegir Supabase** si además se quiere aprovechar su dashboard/auth a futuro.

---

## 4. Scraper — GitHub Actions cron

En vez de un contenedor `scraper` corriendo siempre (como en
`docker-compose.yml`, perfil `tools`), correrlo como job programado:

```yaml
# .github/workflows/scraper.yml
name: scraper
on:
  schedule:
    - cron: "0 */6 * * *"  # cada 6 horas, ajustar según necesidad
  workflow_dispatch: {}

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pip install https://github.com/explosion/spacy-models/releases/download/es_core_news_lg-3.8.0/es_core_news_lg-3.8.0-py3-none-any.whl
      - run: python main.py
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

- GitHub Actions free: 2000 min/mes en repos privados (ilimitado en
  públicos) — de sobra para un scraper corriendo cada pocas horas.
- Alternativa: Cloud Run Jobs + Cloud Scheduler, si se prefiere mantener
  todo dentro de GCP y reusar la misma imagen del backend (`Dockerfile.backend`
  ya soporta `command: ["python", "main.py"]`).

---

## Trade-offs generales de esta configuración gratis

- **Cold starts**: tanto Cloud Run como Neon "duermen" tras inactividad;
  la primera carga tras un rato sin uso puede tardar 5–15s.
- **Sin SLA**: aceptable para que el cliente pruebe funcionalidad, no para
  tráfico de producción o uso crítico.
- **Límites de free tier**: si el cliente valida el producto y se decide
  avanzar, migrar a planes pagos (Cloud Run con min-instances > 0 para
  evitar cold start, Postgres dedicado, etc.).
- **`GEMINI_API_KEY`**: no usar el analyzer de Gemini en este ambiente de
  prueba salvo pedido explícito del cliente — cada llamada tiene costo
  (ver `CLAUDE.md`). Mantener `LocalAnalyzer` (spaCy + pysentimiento) como
  default también en el deploy de prueba.

## Próximos pasos sugeridos

1. Confirmar con el cliente qué tan tolerable es el cold start (define si
   vale la pena mantener alguna instancia mínima paga a futuro).
2. Levantar proyecto en Neon/Supabase y correr migraciones/schema inicial.
3. Deploy de backend en Cloud Run, validar `/docs` (FastAPI) responde.
4. Deploy de frontend en Vercel/Cloudflare Pages, apuntando al backend.
5. Configurar workflow de scraper en GitHub Actions con secret `DATABASE_URL`.
