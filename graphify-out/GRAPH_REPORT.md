# Graph Report - ODIN  (2026-09-03)

## Corpus Check
- 304 files · ~261,925 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3008 nodes · 5594 edges · 260 communities (155 shown, 57 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 519 edges (avg confidence: 0.9)
- Token cost: 572,098 input · 0 output

## Community Hubs (Navigation)
- Design Handoff Runtime
- LLM Analyzers (Gemini/Groq)
- Entity Alias Management
- Documentalist Users & KPIs
- Article Service & Schemas
- Frontend API Client Types
- Canonical Entities API
- Architecture Docs & ADRs
- API Routers & Middleware
- API Filter Tests
- Scrape Jobs API
- Locality API Tests
- Localities DB Model
- Local Place Extraction Tests
- Analyze Service Orchestration
- Canonicalization Tests
- DB Test Fixtures
- Auth & Password Hashing
- Dependency Audit Script
- API Tests
- Locality Service
- Analyzer Evaluation Script
- Dominican News Scrapers
- Local Analyzer & Seed
- Local Analyzer Sentiment
- Frontend Dev Dependencies
- Frontend tsconfig (app)
- API Tests
- Article Analysis Tests
- URL Guard (anti-SSRF)
- API Tests
- API Tests
- Report Repair Scripts
- Analyzer Base & Fallback
- Core Pipeline & Scraping
- Scraper Strip Tests
- Word Export API Tests
- Frontend React Dependencies
- Observability Middleware
- Frontend Alias Components
- Frontend App Pages
- Word Export Service Tests
- Source Router & Scraper Tests
- Political Entity Analysis
- Canonical Entities DB
- User DB Model Tests
- API Tests
- Frontend tsconfig (node)
- API Tests
- API Tests
- Alias DB & Merge Scripts
- Locality Service Tests
- Username Generation Tests
- API Tests
- API Tests
- Locality DB Tests
- Evaluate Script Tests
- Core Config & Alembic
- Superpowers Plans & Fixtures
- Word Export Service
- Frontend API Client
- Evaluate Script
- Local Analyzer Tests
- API Tests
- Planning Docs
- Tests
- Scraper Tests
- Core Tests
- Design Handoff
- Scraper Tests
- Canonicalization Tests
- Local Analyzer
- Scraper Tests
- Service Tests
- Frontend API Client
- Analyzer Fallback
- Local Analyzer Tests
- API Tests
- API Tests
- DB Layer
- Service Tests
- Entity Verify
- Analysis Engine
- Core Tests
- Scraper Tests
- Locality DB Tests
- User DB Tests
- API Routers
- Script Tests
- Local Analyzer Tests
- Analysis Tests
- Core Tests
- Core Tests
- Scrapers
- Packaging Tests
- Docs
- DB Layer
- Frontend API Client
- Frontend API Client
- Frontend Pages
- Analysis Tests
- Analysis Tests
- Local Analyzer Tests
- API Tests
- Frontend
- Frontend Components
- Frontend API Client
- Frontend Pages
- Local Analyzer Tests
- Local Analyzer Tests
- API Routers
- Scraper Tests
- Frontend Dependencies
- Frontend Components
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Frontend Pages
- Frontend Pages
- API Routers
- Superpowers Plans
- Icon Sprite Sheet
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Frontend Pages
- Script Tests
- Canonicalization Tests
- Analysis Tests
- Local Analyzer Tests
- API Tests
- Export Service Tests
- Docs
- Frontend Components
- Frontend Components
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Frontend Pages
- Analysis Tests
- Analysis Tests
- API Tests
- DB Tests
- Design Handoff
- Superpowers Plans
- Frontend Dependencies
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend API Client
- Frontend API Client
- Scripts
- Analysis Tests
- API Routers
- API Routers
- API Tests
- Favicon
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend API Client
- Frontend API Client
- Frontend Pages
- Scripts
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend Components
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Frontend Pages
- Frontend Pages
- Frontend tsconfig
- API Routers
- Misc
- Misc
- Frontend Dependencies
- Frontend Dependencies
- Frontend Dependencies
- Frontend Dependencies
- Frontend Dependencies
- Frontend Dependencies
- Frontend Dependencies
- Frontend Components
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Frontend API Client
- Misc

## God Nodes (most connected - your core abstractions)
1. `sqlite_sessionmaker()` - 120 edges
2. `Article` - 64 edges
3. `EntityResult` - 52 edges
4. `LocalAnalyzer` - 51 edges
5. `Entity` - 50 edges
6. `CanonicalEntity` - 45 edges
7. `User` - 43 edges
8. `AnalysisResult` - 39 edges
9. `react` - 27 edges
10. `norm_key()` - 27 edges

## Surprising Connections (you probably didn't know these)
- `Flujo de Git de Odin (branch dev, worktree solo si hay riesgo)` --semantically_similar_to--> `Flujo de Git de Odin (branch dev, sin commits del agente)`  [INFERRED] [semantically similar]
  CLAUDE.md → AGENTS.md
- `main()` --uses--> `LocalAnalyzer`  [INFERRED]
  scripts/estimate_sentiment_prior.py → src/odin/analysis/local_analyzer.py
- `main()` --uses--> `Article`  [INFERRED]
  scripts/estimate_sentiment_prior.py → src/odin/db/models.py
- `TestEvaluateEndToEnd` --uses--> `GoldEntity`  [INFERRED]
  tests/scripts/test_evaluate.py → scripts/evaluate.py
- `_match_entities()` --uses--> `EntityResult`  [INFERRED]
  scripts/evaluate.py → src/odin/analysis/base.py

## Import Cycles
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/canonical_entities.py -> src/odin/services/canonical_entity_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/articles.py -> src/odin/services/article_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/users.py -> src/odin/services/documentalist_kpi_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/articles.py -> src/odin/services/export_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/localities.py -> src/odin/services/locality_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/aliases.py -> src/odin/services/alias_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/entities.py -> src/odin/services/entity_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/scrape_jobs.py -> src/odin/services/scrape_job_service.py -> src/odin/api/__init__.py`
- 3-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/users.py -> src/odin/services/user_service.py -> src/odin/api/__init__.py`
- 4-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/canonical_entities.py -> src/odin/services/canonical_entity_service.py -> src/odin/services/article_service.py -> src/odin/api/__init__.py`
- 4-file cycle: `src/odin/api/__init__.py -> src/odin/api/routers/aliases.py -> src/odin/services/alias_service.py -> src/odin/services/article_service.py -> src/odin/api/__init__.py`

## Hyperedges (group relationships)
- **Motor de análisis intercambiable (Analyzer + 5 implementaciones)** — docs_procesos_analyzer_interface, docs_procesos_local_analyzer, docs_procesos_gemini_analyzer, docs_procesos_groq_analyzer, docs_procesos_hybrid_analyzer, docs_procesos_groq_with_gemini_fallback [EXTRACTED 1.00]
- **Modelo dimensional de entidades (mención vs dimensión canónica)** — docs_data_dictionary_articles, docs_data_dictionary_entities, docs_data_dictionary_canonical_entities, docs_arquitectura_canonicalize [EXTRACTED 1.00]
- **Flujo POST /api/analyze a demanda** — docs_procesos_flujo_a_demanda, docs_arquitectura_analyze_flow, readme_url_guard, docs_data_dictionary_analyze_jobs, docs_arquitectura_canonicalize, docs_procesos_analyzer_interface [EXTRACTED 1.00]
- **Bucle de evaluación de analizadores contra el golden set** — tests_eval_readme_golden_set, tests_eval_readme_evaluate_script, docs_superpowers_plans_2026_08_14_local_analyzer_accuracy_localanalyzer, docs_planning_conflicts_prompt_unmeasured, docs_superpowers_plans_2026_08_14_local_analyzer_accuracy [EXTRACTED 0.90]
- **Requerimientos del cliente → hoja de ruta por fases** — docs_planning_2026_08_21_requerimientos_cliente_gap, docs_planning_2026_08_21_requerimientos_cliente_gap_client_requirements, docs_planning_2026_08_21_requerimientos_cliente_gap_fases, docs_planning_2026_08_21_requerimientos_cliente_gap_dimensional_model, docs_superpowers_plans_2026_08_22_analistas_autoria_kpi [EXTRACTED 0.80]
- **Bundle de handoff del rediseño de UI de Odin** — docs_design_handoff_odin_redesign_design_handoff, docs_design_handoff_odin_redesign_readme, docs_design_handoff_odin_redesign_task, docs_design_handoff_odin_redesign_odin_dc, docs_design_handoff_odin_redesign_readme_design_tokens, docs_design_handoff_odin_redesign_readme_plasma [EXTRACTED 0.90]
- **Icon Sprite Sheet Symbols** — frontend_public_icons_bluesky, frontend_public_icons_discord, frontend_public_icons_documentation, frontend_public_icons_github, frontend_public_icons_social, frontend_public_icons_x [EXTRACTED 1.00]

## Communities (260 total, 57 thin omitted)

### Community 0 - "Design Handoff Runtime"
Cohesion: 0.06
Nodes (75): boot(), bundledBlob(), cdnScriptFor(), collectProps(), compileAttr(), compileTemplate(), contentKey(), createComponentFactory() (+67 more)

### Community 1 - "LLM Analyzers (Gemini/Groq)"
Cohesion: 0.05
Nodes (45): RuntimeError, _count(), _fold(), Contraste de las entidades que devuelve un LLM contra el texto real. Un LLM…, Minúsculas, sin acentos y con los espacios colapsados, para que un nombre…, Descarta las entidades sin ningún rastro en el texto y baja la confianza de las…, Reemplaza in-place el `mentions_count` estimado por el LLM con el conteo real,…, recount_mentions() (+37 more)

### Community 2 - "Entity Alias Management"
Cohesion: 0.05
Nodes (41): ColumnElement, create_alias(), delete_alias(), list_aliases(), AliasPayload, AliasUpdatePayload, delete, get (+33 more)

### Community 3 - "Documentalist Users & KPIs"
Cohesion: 0.06
Nodes (50): DocumentalistCreated, DocumentalistKpiRow, Dependencias compartidas por los routers: sesión de BD y el analizador activo…, create_documentalist(), documentalist_kpi(), list_documentalists(), DocumentalistPayload, DocumentalistUpdatePayload (+42 more)

### Community 4 - "Article Service & Schemas"
Cohesion: 0.07
Nodes (44): ArticleListResponse, ArticleSummary, invalidate_person_map(), Descarta la caché de `known_person_fullname_map`. La llaman los puntos que…, list_articles(), Lista reportes guardados con filtros combinables. Devuelve resúmenes (sin…, EntityUpdatePayload, put (+36 more)

### Community 5 - "Frontend API Client Types"
Cohesion: 0.04
Nodes (42): AliasPayload, AliasUpdatePayload, AnalyzePreviewEntity, AnalyzeResult, AnalyzeStage, ArticleAnalysis, ArticleFilterOptions, ArticleListParams (+34 more)

### Community 6 - "Canonical Entities API"
Cohesion: 0.08
Nodes (44): CanonicalEntityListResponse, get_canonical_entity(), list_canonical_entities(), merge_canonical_entities(), CanonicalEntityUpdatePayload, get, post, put (+36 more)

### Community 7 - "Architecture Docs & ADRs"
Cohesion: 0.07
Nodes (45): Front-End Validation Protocol (tsc --noEmit, lint, tests), CI (lint, types, test, test-windows, pip-audit), Checkpoint de frescura de documentación (check_docs_freshness.py), Ganchos pre-commit (ruff, mypy, checks), No ejecutar pruebas automatizadas contra la API de Gemini (control de costo), Conflicto npm ci ERESOLVE (typescript ~6 vs openapi-typescript ^5.x), Servicios Docker Compose (db, backend, frontend, scraper), trafilatura + sitemaps/RSS sobre selectores CSS (+37 more)

### Community 8 - "API Routers & Middleware"
Cohesion: 0.06
Nodes (37): ArticleUpdatePayload, FastAPI, middleware, _observability_middleware(), Request, API REST de Odin (FastAPI). Flujo en dos pasos: 1. POST /api/analyze — si la…, Correlation ID + logs estructurados + métricas de latencia/error por endpoint…, _route_template() (+29 more)

### Community 9 - "API Filter Tests"
Cohesion: 0.11
Nodes (22): sessionmaker, documentalist(), fixture, _auth_headers(), _make_article(), Pruebas de los filtros combinables de GET /api/articles (api.py). Usan SQLite…, `topic` filtra por `main_topic`, que hoy es texto libre (no hay catálogo…, Escribir "policía" tiene que alcanzar sus variantes: es lo que rescata algo de… (+14 more)

### Community 10 - "Scrape Jobs API"
Cohesion: 0.09
Nodes (37): cancel_scrape_job(), get_scrape_job(), list_crawl_runs(), list_scrape_jobs(), BackgroundTasks, get, post, Historial de corridas del pipeline (`/api/crawl-runs`) y corridas encoladas del… (+29 more)

### Community 11 - "Locality API Tests"
Cohesion: 0.11
Nodes (17): _auth_headers(), _locality_id(), _make_article(), fixture, Pruebas de /api/localities y del lugar de la noticia. Lo que más importa aquí…, El caso real: el Congreso crea un municipio y el cliente lo agrega sin esperar…, El frontend muestra "RD › Cibao › Santiago › Tamboril" sin tener que subir el…, Todas" en el formulario del cliente = ámbito nacional, y eso se guarda… (+9 more)

### Community 12 - "Localities DB Model"
Cohesion: 0.09
Nodes (31): norm_key(), Clave de comparación: sin acentos, minúsculas, espacios colapsados. Guiones ->…, LocalityResponse, _flatten(), load_seed(), Locality, Session, Catálogo geográfico: carga de la semilla y resolución de nombres. El árbol vive… (+23 more)

### Community 13 - "Local Place Extraction Tests"
Cohesion: 0.07
Nodes (27): Carga los modelos locales antes del primer request. `LocalAnalyzer` los carga…, _warm_up_analyzer(), analyzer(), _keys(), places_68(), fixture, Extracción de lugares (entidades LOC de spaCy) en LocalAnalyzer. Usa el modelo…, La prensa alterna "San Juan" y "provincia San Juan" en la misma nota. Sin… (+19 more)

### Community 14 - "Analyze Service Orchestration"
Cohesion: 0.09
Nodes (33): AnalyzeResult, NamedTuple, canonicalize_result(), Canonicaliza in-place un AnalysisResult completo: entidades + los campos de…, True si el texto contiene alguna palabra de `_VENUE_WORDS` (chequeo léxico…, sentence_mentions_venue_word(), AnalyzePreviewEntity, AnalyzeResult (+25 more)

### Community 15 - "Canonicalization Tests"
Cohesion: 0.13
Nodes (14): EntityResult, _apply_alias_catalog(), canonicalize_entities(), _merge_duplicates(), Sustituye in-place el nombre por el canónico del catálogo de siglas. El tipo…, Abinader" -> "Luis Abinader" cuando la BD solo conoce un Abinader., Funde entidades con el mismo (nombre normalizado, tipo) y las que están…, Aplica los pasos y devuelve la lista canonicalizada (puede ser más corta que la… (+6 more)

### Community 16 - "DB Test Fixtures"
Cohesion: 0.07
Nodes (23): api_client(), _clear_process_caches(), db_session(), fixture, Fixtures compartidas. Todas las pruebas de BD/API usan SQLite en memoria, nunca…, Implementa el operador `~*` de Postgres sobre SQLite: el código de producción…, Vacía las cachés en memoria antes de cada test. `db.aliases` y…, TestClient de la API con `get_session` apuntando a SQLite en memoria. Se… (+15 more)

### Community 17 - "Auth & Password Hashing"
Cohesion: 0.09
Nodes (30): HTTPAuthorizationCredentials, main(), Genera el hash de una contraseña para ODIN_AUTH_PASSWORD_HASH. Uso: python…, authenticate(), _b64e(), change_password(), ChangePasswordRequest, _decode() (+22 more)

### Community 18 - "Dependency Audit Script"
Cohesion: 0.12
Nodes (31): build_report(), bump_kind(), collect_npm_updates(), collect_python_updates(), collect_python_vulns(), fmt_severity(), http_json(), load_dotenv() (+23 more)

### Community 19 - "API Tests"
Cohesion: 0.16
Nodes (16): _admin(), _bearer(), _create(), _headers(), _login(), Alta con PIN de 4 dígitos y cambio obligatorio de contraseña. El PIN es una…, Rescata a quien entró con el PIN y cerró antes de cambiar la clave., El portón vive en la API, no solo en la pantalla: si estuviera solo en el… (+8 more)

### Community 20 - "Locality Service"
Cohesion: 0.14
Nodes (27): ArticleLocality, delete_article_locality(), delete, ArticleLocalityPayload, ArticleLocalityResponse, Alta de un vínculo artículo↔lugar. `locality_id` a secas, sin…, ArticleLocality, Vínculo N:M entre un artículo y un lugar. N:M y no una columna `location_id` en… (+19 more)

### Community 21 - "Analyzer Evaluation Script"
Cohesion: 0.16
Nodes (12): EntityMetrics, GoldEntity, _match_entities(), CONDICIONAL a haber detectado la entidad. Su denominador cambia cuando cambia…, End-to-end: cuenta como fallo la entidad etiquetada que ni siquiera se extrajo.…, De las etiquetas polares emitidas, cuántas coinciden con el gold. Es la cifra…, Empareja predicción <-> gold por (tipo, nombre normalizado con contención).…, _update_metrics() (+4 more)

### Community 22 - "Dominican News Scrapers"
Cohesion: 0.14
Nodes (19): Limpieza del campo de autores. Módulo aparte para que `base.py` pueda usarlo…, Quita del campo de autores las partes que sean el nombre del medio. Varios…, strip_outlet(), BaseScraper, Scraper base para periódicos. Estrategia general (funciona para la mayoría de…, DiarioLibreScraper, Scraper de Diario Libre. Diario Libre publica feeds RSS por sección, así que…, AcentoScraper (+11 more)

### Community 23 - "Local Analyzer & Seed"
Cohesion: 0.11
Nodes (19): Counter, _best_display_name(), _has_nickname_splice(), _place_role(), _preceded_by_admin_unit(), Analizador local (gratis) en español. Combina: - spaCy (es_core_news_lg) ->…, True si `name` tiene un segmento entre guiones/paréntesis/comillas con texto…, Nombres y alias del catálogo geográfico, normalizados. Se leen de la semilla… (+11 more)

### Community 24 - "Local Analyzer Sentiment"
Cohesion: 0.11
Nodes (11): LocalAnalyzer, Iniciales de las palabras significativas de un nombre normalizado., Fusiona 'Policía' dentro de 'Policía Nacional' (subcadena por palabras) y 'FDD'…, Analiza varios artículos en una sola pasada de spaCy (`nlp.pipe`). Evita el…, Solo `(main_topic, topic_keywords)`, sin entidades ni sentimiento. Para quien…, Solo los lugares, sin entidades, tema ni sentimiento. Espeja `analyze_topics`,…, Probabilidades por frase, calculando cada frase ÚNICA una sola vez., Igual que `self.sent.predict(texts)`, pero sin pasar por `Trainer.predict()` de… (+3 more)

### Community 25 - "Frontend Dev Dependencies"
Cohesion: 0.07
Nodes (27): devDependencies, jsdom, openapi-typescript, @testing-library/dom, @testing-library/jest-dom, @testing-library/react, @testing-library/user-event, @types/node (+19 more)

### Community 26 - "Frontend tsconfig (app)"
Cohesion: 0.07
Nodes (26): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+18 more)

### Community 27 - "API Tests"
Cohesion: 0.15
Nodes (10): CanonicalEntity, Dimensión de personas/organizaciones: una fila por figura real.…, _auth_headers(), _make_article(), Pruebas de /api/canonical-entities (api.py): listado con conteos, detalle,…, TestGetCanonicalEntity, TestListCanonicalEntities, TestMergeCanonicalEntities (+2 more)

### Community 28 - "Article Analysis Tests"
Cohesion: 0.18
Nodes (9): Entity, _auth_headers(), Pruebas de los endpoints de borrado/rectificación de artículos y menciones de…, _seed_article(), _seed_entity(), TestDeleteArticle, TestDeleteEntity, TestUpdateArticle (+1 more)

### Community 29 - "URL Guard (anti-SSRF)"
Cohesion: 0.12
Nodes (24): IPv4Address, IPv6Address, _assert_resolves_to_public_ip(), _charset_from_content_type(), _content_type_allowed(), _decode_html(), fetch_html(), _host_allowed() (+16 more)

### Community 30 - "API Tests"
Cohesion: 0.14
Nodes (11): _auth_headers(), _fake_analysis_result(), Pruebas de POST /api/analyze → 202 + job_id y GET /api/jobs/{id} (§3.1 de…, Los fallos previstos (`HTTPException`) llevan un texto pensado para el usuario:…, Una excepción imprevista no debe salir cruda en el UI: el detalle va al log y…, Cada análisis evitado es una llamada al LLM que no se hace (y en modo…, Parchea el pipeline contando cuántas veces se analiza de verdad., Doble del análisis, construido con el `AnalysisResult` REAL. Antes era una… (+3 more)

### Community 31 - "API Tests"
Cohesion: 0.15
Nodes (11): _headers(), _payload(), Pruebas de la autoría del reporte. `documentalist` (persona) y `analyzer_name`…, Lo que entra por el rastreo masivo no tiene persona detrás., Si otra persona corrige el análisis, el reporte pasa a ser suyo: el KPI mide…, Un token válido de alguien ya borrado no puede tumbar el guardado., La atribución por documentalista son nombres de personal: el listado no puede…, El listado carga el documentalista en bloque, no una consulta por fila: son 20… (+3 more)

### Community 32 - "Report Repair Scripts"
Cohesion: 0.13
Nodes (18): DeclarativeBase, _Cambio, main(), Repara el medio y los autores de reportes ya guardados. Por qué hace falta:…, Lo que se le va a escribir a un reporte. `authors_cambia` es un campo aparte y…, entity_report(), main(), Consultas rápidas sobre lo guardado (para revisar resultados sin SQL a mano).… (+10 more)

### Community 33 - "Analyzer Base & Fallback"
Cohesion: 0.12
Nodes (11): Protocol, _dry_run(), main(), Rastrea las 8 fuentes permitidas filtrando solo noticias de política de RD,…, Solo cuenta cuántos artículos de política habría por fuente, sin analizar ni…, Analyzer, Interfaz del analizador. El resto del sistema (scraper, base de datos,…, Groq primero, Gemini como red de seguridad. Motivo: `GroqAnalyzer` es gratis… (+3 more)

### Community 34 - "Core Pipeline & Scraping"
Cohesion: 0.14
Nodes (21): make_filter(), Cierre con estado: decide qué artículos entran, respetando el tope global y el…, correlation_scope(), new_correlation_id(), Fija el correlation ID activo durante el bloque `with`., _already_stored(), _finish_crawl_run(), Pipeline principal: scrape -> analizar -> guardar. Orquesta los scrapers y el… (+13 more)

### Community 35 - "Scraper Strip Tests"
Cohesion: 0.13
Nodes (10): Quita el nombre del medio del campo de autores. Ver `authors.strip_outlet`.…, strip_outlet_from_authors(), parametrize, El medio no es un autor. Trafilatura devuelve el campo `author` tal como lo…, El sitio escribe "Listin" sin tilde; el registro, "Listín"., Diario" suelto no es el medio: solo se quita la coincidencia exacta., Algunos sitios ponen su dominio en el campo autor, con formato de nombre. Salió…, TestLeavesEverythingElseAlone (+2 more)

### Community 36 - "Word Export API Tests"
Cohesion: 0.13
Nodes (12): _doc(), _export(), _headers(), Document, fixture, El .docx exportado sigue la plantilla de docs/export 4. Se usa el .docx como…, La plantilla trae dos reportes de muestra que no deben viajar., reports() (+4 more)

### Community 37 - "Frontend React Dependencies"
Cohesion: 0.09
Nodes (23): @base-ui/react, class-variance-authority, clsx, @fontsource/ibm-plex-sans, framer-motion, dependencies, @base-ui/react, class-variance-authority (+15 more)

### Community 38 - "Observability Middleware"
Cohesion: 0.13
Nodes (17): BoundLogger, Histogram, HybridAnalyzer, LocalAnalyzer (gratis) SOLO para tema/keywords/sentimiento global + Groq para…, main(), CLI de Odin. Ejemplos: odin --init-db # solo crear tablas odin # rastrear ambos…, _add_correlation_id(), configure_logging() (+9 more)

### Community 39 - "Frontend Alias Components"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 40 - "Frontend App Pages"
Cohesion: 0.10
Nodes (6): App(), getInitialTheme(), Theme, UsersCard(), ChangePasswordPage(), react

### Community 41 - "Word Export Service Tests"
Cohesion: 0.13
Nodes (12): clean_body(), _is_section_kicker(), ¿Es un ladillo de sección y no un párrafo de la nota? Se exige que sea corto Y…, Párrafos del cuerpo, sin lo que arrastra el scrape. Lo que viene del sitio…, Limpieza del cuerpo scrapeado antes de exportarlo a Word. Lo que llega del…, El scrape a veces devuelve el titular en otra caja., De un párrafo repetido se conserva la ÚLTIMA aparición. El caso real es el…, Alegada negligencia" es un ladillo del medio, no un párrafo. (+4 more)

### Community 42 - "Source Router & Scraper Tests"
Cohesion: 0.12
Nodes (17): SourceOption, article_filters(), get_article(), list_sources(), get, Reporte completo (con entidades) de un artículo ya guardado., Valores disponibles para poblar los selectores de filtro del frontend. Fuentes…, Medios disponibles para el formulario de captura, desde el registro de… (+9 more)

### Community 43 - "Political Entity Analysis"
Cohesion: 0.14
Nodes (14): Canonicalización de entidades: un solo nombre por figura/empresa. Resuelve el…, Elimina un título de cortesía del inicio del nombre, si lo hay., _strip_title_prefix(), _compile_politics_pattern(), is_dominican_politics(), Pattern, Clasificador por palabras clave: ¿es este artículo de política dominicana?…, Un solo término suelto en el cuerpo no basta: la prensa dominicana namedropea… (+6 more)

### Community 44 - "Canonical Entities DB"
Cohesion: 0.15
Nodes (11): get_or_create(), merge(), CanonicalEntity, Session, Devuelve la `CanonicalEntity` para (name, type), creándola si no existe.…, Resuelve un actor de encuadre (`dominant_actor`/`blamed_actor`/…, Funde `source_id` dentro de `target_id`: reasigna todas las menciones…, resolve_actor_id() (+3 more)

### Community 45 - "User DB Model Tests"
Cohesion: 0.11
Nodes (11): Una persona que usa Odin. Hasta ahora la autenticación era un operador único…, Mantiene `username_key` derivado de `username` en TODA escritura. Un `default`…, User, documentalist(), fixture, `seed_operator` (db/users.py) solo siembra al primer admin cuando la tabla…, TestLastAdminGuard, Quien teclea "JPerez" al entrar es la misma persona que "jperez". (+3 more)

### Community 46 - "API Tests"
Cohesion: 0.21
Nodes (12): _auth_headers(), _count(), _locality_id(), _payload(), fixture, Alta manual de un reporte: artículo y lugares en una sola escritura. El…, Una nota puede ocurrir en Santiago y además mencionar a Santiago., El flujo de AnalyzePage no manda el campo: tiene que seguir igual. (+4 more)

### Community 47 - "Frontend tsconfig (node)"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+11 more)

### Community 48 - "API Tests"
Cohesion: 0.15
Nodes (10): _headers(), people(), fixture, Pruebas del CRUD de documentalistas., Ya no hay 409 por usuario repetido: como el usuario se autogenera, rechazar el…, Un hash filtrado es un ataque offline servido en bandeja., El alta ya no recibe contraseña: devuelve un PIN de primer acceso. Las reglas…, TestCreate (+2 more)

### Community 49 - "API Tests"
Cohesion: 0.17
Nodes (10): _headers(), Document, fixture, Pruebas de la exportación a Word. El caso del cliente: el admin filtra los…, Un id borrado entre que se listó y se exportó no puede tumbar la descarga…, El documento lo lee el cliente: "Listín Diario", no `listin_diario`., Es el dato que hace útil el documento cuando se exporta el trabajo de una…, _read() (+2 more)

### Community 50 - "Alias DB & Merge Scripts"
Cohesion: 0.16
Nodes (17): _canonical_name(), main(), Unifica entidades duplicadas YA guardadas en la BD. Aplica retroactivamente la…, Nombre y tipo canónicos para una fila existente (aliases + apellido)., _lifespan(), Crea tablas, carga el catálogo semilla, repara los jobs que quedaron a medias y…, all_canonicals(), _build_cache() (+9 more)

### Community 51 - "Locality Service Tests"
Cohesion: 0.17
Nodes (18): PlaceResult, Un lugar candidato, TAL COMO APARECIÓ EN EL TEXTO. Deliberadamente sin…, Resuelve los candidatos del analizador contra el catálogo vivo. Descarta en…, suggest_from_places(), SuggestedLocality, fixture, Candidatos crudos del analizador -> nodos reales del catálogo. Es la frontera…, Sesión SQLite (fixture `db_session` de tests/conftest.py) con el catálogo real… (+10 more)

### Community 52 - "Username Generation Tests"
Cohesion: 0.15
Nodes (10): _ascii_letters(), Deja solo letras a-z, sin acentos ni ñ, en minúsculas. NFKD separa la letra de…, Inicial del nombre + 4 primeras letras del apellido: "Yvan Mercado" -> "ymerc".…, username_from_name(), parametrize, Usuario derivado del nombre: inicial del nombre + 4 primeras del apellido. La…, De la Cruz" es UN apellido; se toman sus 4 primeras letras., TestBasicRule (+2 more)

### Community 53 - "API Tests"
Cohesion: 0.15
Nodes (9): _headers(), fixture, Pruebas del resumen de trabajo por documentalista. Es material de evaluación,…, Los números de productividad no son para los compañeros., El frontend necesita el rol para ocultar lo que es solo de admin., Tres reportes en dos días son dos días de trabajo, no tres., team(), TestKpi (+1 more)

### Community 54 - "API Tests"
Cohesion: 0.22
Nodes (9): _auth(), Orden del listado de reportes por columna. `sort` era campo y dirección en un…, C no tiene fecha de análisis. Sin esto, descendente lo pondría arriba y la…, _seed(), TestBackwardCompatibility, TestRejectsNonsense, TestSortByAnalyzedOn, TestSortBySource (+1 more)

### Community 55 - "Locality DB Tests"
Cohesion: 0.12
Nodes (9): _count(), Pruebas del catálogo geográfico (`odin/db/localities.py`). La cifra que se…, Sin la barra final, LIKE '/1/2%' matchearía también al id 20., Un alias agregado al JSON tiene que llegar a una base ya sembrada. Antes se…, El DN no es provincia ni se divide en municipios: modelarlo con uno propio…, La Victoria (Ley 15-24, vigente desde 2026-01-01) y La Caleta (Ley 39-24)…, TestPath, TestSeed (+1 more)

### Community 56 - "Evaluate Script Tests"
Cohesion: 0.33
Nodes (9): evaluate(), GoldArticle, AnalysisResult, Pruebas de scripts/evaluate.py: emparejamiento de entidades, agregación de…, Devuelve resultados fijos por título, para probar `evaluate()` sin cargar…, _StubAnalyzer, TestCategoryMetrics, TestEvaluateEndToEnd (+1 more)

### Community 57 - "Core Config & Alembic"
Cohesion: 0.12
Nodes (13): Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online(), Vuelca el schema OpenAPI real de la API a un archivo JSON (tarea 25 de task.md,…, _choice(), _csv(), _flag() (+5 more)

### Community 58 - "Superpowers Plans & Fixtures"
Cohesion: 0.22
Nodes (17): O4: blamed_actor vacío justo en las denuncias (señalado genérico no nombrado), Conflictos de diseño de Odin, Conflicto 3: modelo de entidades plano vs relaciones fuente→objetivo, Conflicto 4: se cambió el prompt v5→v6 sin poder medir el efecto, Techo estructural de sentiment_toward (piso trivial NEU 71.5%), Plan: LocalAnalyzer Accuracy, _best_display_name (elegir nombre más completo, no el más frecuente), Dejar de filtrar 'Gobierno' como ORG genérico (_GENERIC_STATE_ORGS) (+9 more)

### Community 59 - "Word Export Service"
Cohesion: 0.18
Nodes (16): DocxDocument, _add_field(), _add_meta(), build_document(), export_articles(), _format_date(), _load_template(), _period() (+8 more)

### Community 60 - "Frontend API Client"
Cohesion: 0.14
Nodes (11): ALL, EMPTY_CHOICE, filterLocalities(), indexTree(), LocalityEntry, LocalityIndex, normalizeText(), PickedLocality (+3 more)

### Community 61 - "Evaluate Script"
Cohesion: 0.20
Nodes (12): _build_analyzer(), _fmt(), load_golden_set(), main(), Any, Path, Evalúa un analizador contra el golden set (tests/eval/golden_set.jsonl).…, content_flags es multi-etiqueta (0..N banderas por artículo, no una categoría… (+4 more)

### Community 62 - "Local Analyzer Tests"
Cohesion: 0.18
Nodes (10): _is_named_after_place(), _preceded_by_venue_noun(), Mira hacia atrás desde la entidad (la más cercana primero); se detiene al…, Sube por la cadena de dependencias desde la entidad buscando una cabeza tipo…, nlp(), _person_ents(), fixture, Pruebas de analysis/local_analyzer.py sobre las heurísticas de lugar vs.… (+2 more)

### Community 63 - "API Tests"
Cohesion: 0.24
Nodes (8): _admin(), _create(), _headers(), Alta con nombre y apellido: el usuario se autogenera y nunca choca., El login compara en minúsculas, así que el choque también., Lo que importa del sufijo: que sean cuentas distintas de verdad., TestCollisions, TestGeneratedUsername

### Community 64 - "Planning Docs"
Cohesion: 0.18
Nodes (16): Requerimientos del cliente vs Odin actual — análisis de brecha, Decisión D1: censo de titulares vs análisis a demanda, Requerimientos del cliente R1–R22 (watchlist, temas, lugar, hechos, KPI, export), Cambio de forma: modelo dimensional (medio·periodista·tema·lugar·hecho) para Power BI, Fases propuestas F0–F6 (fundación dimensional, temas, roles, seguimiento, prominencia, documentalistas, hechos), Decisión D3: watchlist acotada de actores/instituciones, Oportunidades de mejora del pipeline de análisis, O1: detectar canónicas duplicadas por subconjunto de tokens (sugerir, no fusionar) (+8 more)

### Community 65 - "Tests"
Cohesion: 0.18
Nodes (9): create_token(), Devuelve (token, segundos_de_vigencia). `must_change_password` viaja como claim…, _auth_headers(), _make_article(), Pruebas de los quick wins de task.md §11 (#2, #3, #4, #5, #10): #2 init_db() ya…, TestHealthCheck, TestInitDbNotOnHotPath, TestLikeEscaping (+1 more)

### Community 66 - "Scraper Tests"
Cohesion: 0.19
Nodes (5): _DomainThrottle, Cortesía real por dominio (§2.6 de task.md): garantiza al menos…, Pruebas de los parsers puros de odin/scrapers/base.py: `_parse_date` y…, TestDomainThrottle, TestFetchRespectsRobotsAndThrottle

### Community 67 - "Core Tests"
Cohesion: 0.17
Nodes (5): _FakeResponse, Pruebas de la decodificación de HTML en url_guard.py (ruta de POST…, Lo único que `_decode_html` mira de la respuesta es el Content-Type., TestCharsetFromContentType, TestDecodeHtml

### Community 68 - "Design Handoff"
Cohesion: 0.28
Nodes (15): Odin Design Handoff (estado actual del frontend), Aurora / SoftAurora (fondo WebGL actual, a eliminar), Odin (herramienta interna de monitoreo de prensa dominicana), Odin.dc.html prototipo hifi, Handoff: rediseño de UI de Odin (spec principal), Diálogo de confirmación propio (reemplaza window.confirm), Sistema de design tokens (claro/oscuro, acento Material-like), Tipografía IBM Plex Sans / IBM Plex Mono (+7 more)

### Community 69 - "Scraper Tests"
Cohesion: 0.21
Nodes (4): RobotFileParser, `robots.txt` por dominio, descargado una vez y cacheado. Un dominio que no…, _RobotsCache, TestRobotsCache

### Community 70 - "Canonicalization Tests"
Cohesion: 0.14
Nodes (7): known_person_fullname_map(), Mapa apellido -> nombre completo, construido con los PERSON ya guardados en la…, _no_real_alias_db(), fixture, Pruebas de analysis/canonicalize.py: fusión de entidades, desambiguación por…, TestKnownPersonFullnameMap, TestNormKey

### Community 71 - "Local Analyzer"
Cohesion: 0.14
Nodes (9): _is_institution_head(), _is_proper_span(), Decide, frase por frase, QUÉ entidad recibe cada patrón del léxico relacional.…, Un nombre real casi siempre tiene todos sus tokens como PROPN (spaCy). Filtra…, Las frases del documento ya recortadas, más lo necesario para ubicar una…, Índice de la frase, o None si quedó fuera del tope de frases., Posición de la entidad dentro de `texts[index]`., True si el nombre normalizado ES una cabeza institucional de… (+1 more)

### Community 72 - "Scraper Tests"
Cohesion: 0.17
Nodes (11): _domain_to_source(), Dominio -> clave del medio. Se deduce de los feeds y sitemaps que el scraper ya…, Clave del medio a partir del dominio, o `None` si no se reconoce. Se usa al…, source_from_url(), _domains(), parametrize, Medio deducido del dominio de la URL. Al analizar por URL el medio salía de lo…, Si se agrega un scraper sin feeds ni sitemaps, esto lo delata. (+3 more)

### Community 73 - "Service Tests"
Cohesion: 0.19
Nodes (10): arbiter_calls(), _enable_arbiter(), fixture, El árbitro de entidades ambiguas es una llamada FACTURADA extra a Gemini…, Cuenta las llamadas al árbitro sin tocar la red., Un caso ambiguo de verdad: PERSON cuyo contexto menciona un lugar., El guard miraba solo `ODIN_ANALYZER=gemini`, así que con groq/hybrid/…, _result_with_venue_person() (+2 more)

### Community 74 - "Frontend API Client"
Cohesion: 0.14
Nodes (14): getArticle(), getArticleFilterOptions(), getArticleLocalities(), getCanonicalEntity(), getDocumentalistKpi(), getLocalityTree(), getMe(), listAliases() (+6 more)

### Community 75 - "Analyzer Fallback"
Cohesion: 0.18
Nodes (7): _fallback_reason(), GroqWithGeminiFallback, Exception, Cadena de Gemini a probar EN ORDEN cuando Groq falla. Si hay dos cuentas…, Recorre la cadena hasta que una cuenta responde. La última que falla propaga:…, Clasifica por qué se recurrió al motor de pago, para la métrica…, El motor que produjo el último análisis en este hilo. Antes de la primera…

### Community 76 - "Local Analyzer Tests"
Cohesion: 0.19
Nodes (6): `_GENERIC_STATE_ORGS` filtra "República"/"Estado"/etc. sueltos, pero NO…, spaCy etiqueta "Gobierno" como LOC en la mayoría de los casos (medido: 25 LOC…, Siglas del catálogo curado (db/seed_aliases.py) se resuelven al nombre canónico…, TestGenericStateOrgFilter, TestInstitutionHeadPromotion, TestSeedAliasResolution

### Community 77 - "API Tests"
Cohesion: 0.25
Nodes (8): _auth_headers(), _make_article(), El medio viaja con su nombre legible además del slug. El slug (`listin_diario`)…, La etiqueta es de presentación: el filtro sigue viajando con el slug., Alimenta las sugerencias del campo Tema del formulario manual., TestSourceFacets, TestSourceNameInArticles, TestTopicFacet

### Community 78 - "API Tests"
Cohesion: 0.19
Nodes (7): AnalyzeJob, Trabajo asíncrono de `POST /api/analyze` (§3.1 de task.md). Antes ese endpoint…, Marca como fallidos los jobs que quedaron a medias y borra los viejos.…, reap_stale_jobs(), El handler arma el JSON a mano para no re-serializar el resultado en cada poll;…, TestGetJob, TestReapStaleJobs

### Community 79 - "DB Layer"
Cohesion: 0.18
Nodes (9): get_by_username(), Session, Consultas y siembra de la tabla de documentalistas. La siembra del operador del…, Clave de comparación: sin espacios sobrantes y en minúsculas., Convierte al operador del `.env` en el primer usuario (rol `admin`). Solo actúa…, seed_operator(), username_key(), Pruebas del login contra la tabla de documentalistas. Antes se validaba contra… (+1 more)

### Community 80 - "Service Tests"
Cohesion: 0.21
Nodes (7): Medio de una nota analizada por URL. Orden deliberado: primero el dominio…, resolve_source(), parametrize, El medio de una nota analizada por URL sale del dominio. Antes salía del…, El dominio es un dato duro; el `sitename` es una heurística., Un medio que no rastreamos conserva lo que se pudo extraer: es más informativo…, TestResolveSource

### Community 81 - "Entity Verify"
Cohesion: 0.23
Nodes (11): _align(), are_person_mentions(), is_person_mention(), BaseModel, Árbitro puntual con Gemini: ¿la oración habla DE la persona, o el nombre solo…, Para cada (nombre, oración), True si la oración habla de la persona (no de un…, Caso individual; conveniencia sobre `are_person_mentions`., Un veredicto atado a su caso por número, no por posición. La versión anterior… (+3 more)

### Community 82 - "Analysis Engine"
Cohesion: 0.21
Nodes (11): apply_label_boost(), _boosted(), _compile(), entity_relation_hits(), _label_from(), Pattern, Vocabulario de refuerzo para el sentimiento (POS/NEG/NEU) en cobertura política…, Posición y etiqueta de CADA patrón relacional del texto, ordenadas por… (+3 more)

### Community 83 - "Core Tests"
Cohesion: 0.24
Nodes (6): canonical_url(), Forma canónica de la URL de un artículo, para que la MISMA nota no se analice…, parametrize, Pruebas de `url_guard.canonical_url`: la forma con la que se compara una URL…, test_variants_of_the_same_link_collapse(), TestKeepsWhatChangesTheContent

### Community 84 - "Scraper Tests"
Cohesion: 0.27
Nodes (4): _parse_date(), datetime, Parsea la fecha que devuelve trafilatura (ISO 8601 o solo fecha) y la normaliza…, TestParseDate

### Community 85 - "Locality DB Tests"
Cohesion: 0.17
Nodes (5): La prensa sigue diciendo "Salcedo" por Hermanas Mirabal (renombrada en 2007)., Villa Bisonó aparece en los medios casi siempre como "Navarrete"., Santiago" es provincia y también el nombre corto de su municipio cabecera; sin…, Un alias igual al nombre no aporta y ensucia la tabla., TestResolve

### Community 86 - "User DB Tests"
Cohesion: 0.23
Nodes (6): Pruebas de la tabla de documentalistas y de la siembra del operador del…, Sembrar en cada arranque no debe pisar contraseñas ya cambiadas., Sin contraseña el sistema queda cerrado, no con un admin sin clave., `Settings` es un `@dataclass(frozen=True)`: sus campos NO se pueden mutar…, Quien hoy entra con las credenciales del .env tiene que seguir entrando: se…, TestSeedOperator

### Community 87 - "API Routers"
Cohesion: 0.18
Nodes (11): LocalityNode, list_article_localities(), list_localities(), locality_frequency(), locality_tree(), get, Árbol completo país→municipio, para el selector en cascada., Busca lugares por nombre (sin importar acentos), nivel o lugar padre. (+3 more)

### Community 89 - "Local Analyzer Tests"
Cohesion: 0.25
Nodes (6): _aggregate_entity(), _mean_probas(), Media de probabilidad por etiqueta, ignorando las frases sin puntuar. Devuelve…, Sentimiento HACIA una entidad, sobre las frases donde se la menciona.…, `_aggregate_entity` exige corroboración antes de atribuir una etiqueta polar a…, TestAggregateEntity

### Community 90 - "Analysis Tests"
Cohesion: 0.31
Nodes (3): lexicon_label(), NEG"/"POS" si el texto trae vocabulario GLOBAL de un solo lado del glosario;…, TestLexiconLabel

### Community 91 - "Core Tests"
Cohesion: 0.24
Nodes (6): _b64d(), Compara en tiempo constante contra un hash del formato de arriba. Un hash que…, verify_password(), Un hash almacenado ilegible tiene que distinguirse de una clave equivocada.…, El caso normal no debe ensuciar el log: un 401 legítimo es rutina., TestMalformedStoredHash

### Community 92 - "Core Tests"
Cohesion: 0.33
Nodes (6): _persist(), _FakeAnalyzer, Pruebas de odin/core/pipeline.py: que _persist() vincule cada entidad guardada…, _scraped(), TestPersistLinksCanonicalEntity, TestPersistRecordsLineage

### Community 93 - "Scrapers"
Cohesion: 0.22
Nodes (6): Datos crudos extraídos de un artículo, antes del análisis NLP., Devuelve URLs de artículos a partir de `sitemaps` y `feeds`. Los feeds se…, Descarga con reintentos y backoff exponencial ante errores de red. Antes de…, Extrae los campos del artículo usando trafilatura., Genera artículos extraídos. La descarga se hace de forma concurrente (I/O de…, ScrapedArticle

### Community 94 - "Packaging Tests"
Cohesion: 0.31
Nodes (9): requirements-ci.txt tiene que cubrir todo requirements.txt salvo lo pesado. Los…, test_every_light_requirement_is_in_the_ci_set(), test_the_ci_set_has_no_leftovers(), _declared(), _locked(), _normalize(), El lock tiene que cubrir todo lo declarado en requirements.txt.…, PEP 503: los nombres de paquete no distinguen mayúsculas ni -/_/. entre sí. (+1 more)

### Community 95 - "Docs"
Cohesion: 0.27
Nodes (10): Dockerización de Odin, Stack docker-compose de 4 servicios (db, backend, frontend, scraper perfil tools), Cacheo de dependencias: capas/BuildKit en build vs volúmenes nombrados en runtime, Política de costo de Gemini (no pruebas automatizadas contra la API real), requirements.lock (builds reproducibles con hash, uv pip compile --python-version 3.13), Plan de deploy gratis para pruebas con el cliente, Deploy gratis: Vercel/Cloudflare Pages + Cloud Run + Neon/Supabase + GitHub Actions cron, Exportación de reportes seleccionados a Word (.docx, python-docx) (+2 more)

### Community 96 - "DB Layer"
Cohesion: 0.24
Nodes (9): Engine, _alembic_config(), alembic_head_revision(), get_engine(), _get_sessionmaker(), Motor y sesión de SQLAlchemy. Un solo punto de configuración de conexión.…, Crea (una sola vez) el engine a partir de DATABASE_URL., Localiza `alembic.ini` y devuelve su configuración, o `None`. Se busca en el… (+1 more)

### Community 97 - "Frontend API Client"
Cohesion: 0.22
Nodes (3): AUTH_EXPIRED_EVENT, getRole(), isAdmin()

### Community 98 - "Frontend API Client"
Cohesion: 0.20
Nodes (7): ENTITY_TYPE_LABELS, FRAMING_LABELS, HEADLINE_LABELS, LEAD_LABELS, SENTIMENT_LABELS, SOURCE_LABELS, Tone

### Community 99 - "Frontend Pages"
Cohesion: 0.20
Nodes (4): EMPTY, Field, NewReportPage(), REQUIRED

### Community 100 - "Analysis Tests"
Cohesion: 0.24
Nodes (6): apply_negation_dampening(), dampen_negated(), Si `negated`, acerca POS/NEG a NEU (con `factor=0.5`, reduce a la mitad la…, Combina `has_negation_cue` + `dampen_negated`: atenúa la frase hacia NEU si…, TestApplyNegationDampening, TestDampenNegated

### Community 101 - "Analysis Tests"
Cohesion: 0.22
Nodes (5): lexicon_matches(), Términos del léxico (general + relacional) que matchearon en `text`, para…, Pruebas de odin/analysis/sentiment_lexicon.py: el glosario de refuerzo de…, TestLexiconMatches, TestPromptGlossary

### Community 103 - "API Tests"
Cohesion: 0.29
Nodes (4): _auth_headers(), Catálogo de medios para el formulario de captura manual. Distinto de las…, La BD de la prueba está vacía y aun así vienen los 9: el catálogo sale del…, TestSourceCatalog

### Community 104 - "Frontend"
Cohesion: 0.22
Nodes (8): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema, oxc, typescript, warn

### Community 105 - "Frontend Components"
Cohesion: 0.22
Nodes (3): AliasRow(), EMPTY_FORM, NewAliasForm()

### Community 107 - "Frontend Pages"
Cohesion: 0.28
Nodes (4): AnalyzePage(), handleSubmit(), errorMessage(), toDraft()

### Community 108 - "Local Analyzer Tests"
Cohesion: 0.33
Nodes (4): _aggregate_document(), Sentimiento del ARTÍCULO completo. Combina las frases como evidencia…, `_aggregate_document` descuenta la tasa base por clase para que un artículo no…, TestAggregateDocument

### Community 109 - "Local Analyzer Tests"
Cohesion: 0.36
Nodes (3): _extraction_confidence(), Qué tan segura estuvo la extracción de que esta es una mención real, no ruido.…, TestExtractionConfidence

### Community 110 - "API Routers"
Cohesion: 0.22
Nodes (9): add_article_locality(), create_locality(), ArticleLocalityPayload, post, put, Agrega un lugar al catálogo (p. ej. un municipio creado por ley)., Vincula un lugar al artículo (el botón "Agregar" del formulario)., Deja el artículo exactamente con los lugares enviados. (+1 more)

### Community 111 - "Scraper Tests"
Cohesion: 0.36
Nodes (3): Extrae los <loc> de artículos de un sitemap XML (estándar o Google News). Solo…, _urls_from_sitemap(), TestUrlsFromSitemap

### Community 112 - "Frontend Dependencies"
Cohesion: 0.25
Nodes (8): scripts, build, dev, generate:types, lint, preview, test, test:watch

### Community 113 - "Frontend Components"
Cohesion: 0.25
Nodes (3): ErrorBoundary, Props, State

### Community 115 - "Frontend API Client"
Cohesion: 0.25
Nodes (6): SOFT_AURORA_COLORS, SOFT_AURORA_OPACITY, SOFT_AURORA_PARAMS, SOFT_AURORA_QUALITY, SOFT_AURORA_THEME_PARAMS, Theme

### Community 116 - "Frontend API Client"
Cohesion: 0.25
Nodes (8): putJson(), replaceArticleLocalities(), toggleAlias(), updateAlias(), updateArticle(), updateCanonicalEntity(), updateDocumentalist(), updateEntity()

### Community 118 - "Frontend Pages"
Cohesion: 0.25
Nodes (5): mockedCreate, mockedFacets, mockedSources, mockedTree, navigate

### Community 119 - "Frontend Pages"
Cohesion: 0.32
Nodes (6): EditableFields, ReportDetailPage(), handleDelete(), onBack(), startEditing(), toEditForm()

### Community 120 - "API Routers"
Cohesion: 0.29
Nodes (7): health(), metrics(), get, Chequeos de operación: salud de la BD y métricas Prometheus., Chequeo real: si la BD no responde, `status` refleja el problema en vez de…, Métricas en formato Prometheus (§7.1 de task.md): pipeline, latencia y tasa de…, HealthResponse

### Community 121 - "Superpowers Plans"
Cohesion: 0.43
Nodes (7): Conflicto 1: el esquema no cabe en el free tier de Groq (92% del TPM), Selección explícita de analizador (ODIN_ANALYZER, nunca por presencia de llave), Plan: Toggle de motor de análisis en Ajustes, Toggle de motor de análisis en Ajustes (Cascada vs Solo Local), CascadeAnalyzer (Groq → Gemini → LocalAnalyzer que nunca falla), GroqWithGeminiFallback (Groq → Gemini free → Gemini pago, propaga si el último falla), Tabla runtime_settings (fila única de preferencias configurables sin .env)

### Community 122 - "Icon Sprite Sheet"
Cohesion: 0.43
Nodes (7): Bluesky Icon, Discord Icon, Documentation Icon, GitHub Icon, Social Icon, Frontend Icon Sprite Sheet (icons.svg), X (Twitter) Icon

### Community 123 - "Frontend Components"
Cohesion: 0.29
Nodes (5): ACTOR_FIELDS, AnalysisCard(), AnalysisCardFields, FRAMING_FIELDS, WEIGHT_BY_FIELD

### Community 124 - "Frontend Components"
Cohesion: 0.33
Nodes (3): CanonicalEntityRow(), formatDate(), MergePanel()

### Community 125 - "Frontend Components"
Cohesion: 0.33
Nodes (4): field(), mockedGetTree, ready(), TREE

### Community 127 - "Frontend API Client"
Cohesion: 0.33
Nodes (4): ConfirmOptions, DialogContext, DialogProvider(), PendingDialog

### Community 128 - "Frontend API Client"
Cohesion: 0.29
Nodes (7): addArticleLocality(), createAlias(), createDocumentalist(), mergeCanonicalEntities(), postJson(), resetDocumentalistPin(), saveArticle()

### Community 131 - "Frontend API Client"
Cohesion: 0.43
Nodes (6): bySource(), groupArticlesBySource(), groupSentimentBySource(), ratedMentionVolume(), SourceArticles, SourceSentiment

### Community 132 - "Frontend Pages"
Cohesion: 0.29
Nodes (4): DRAFT, mockedAnalyze, mockedSave, mockedTree

### Community 134 - "Canonicalization Tests"
Cohesion: 0.43
Nodes (3): match_actor_name(), Reapunta un nombre de actor (dominant/blamed/credited) a la entidad…, TestMatchActorName

### Community 135 - "Analysis Tests"
Cohesion: 0.43
Nodes (3): entity_relation_label(), Igual que `lexicon_label`, pero con el léxico RELACIONAL ("acusado de",…, TestEntityRelationLabel

### Community 136 - "Local Analyzer Tests"
Cohesion: 0.29
Nodes (4): Correr el modelo de sentimiento para tirarlo sería ~60% del tiempo. Se verifica…, El caso que reportó el usuario: 'San Juan' en titular y cuerpo., `extract_places` es el camino que usan los motores LLM. Los lugares salen del…, TestExtractPlaces

### Community 138 - "Export Service Tests"
Cohesion: 0.29
Nodes (3): Guarda contra la regresión de empaquetado de la plantilla .docx. Mismo riesgo…, Si alguien reemplaza la plantilla sin estos estilos, el export revienta al…, test_the_template_keeps_the_styles_the_export_writes()

### Community 139 - "Docs"
Cohesion: 0.40
Nodes (6): Odin — Auditoría técnica y backlog de madurez, Mitigación SSRF en POST /api/analyze (url_guard: allowlist + IPs públicas), Agregar más scrapers dominicanos a Odin, Patrón BaseScraper (sitemap/RSS + discover_urls, agregar medio = 4 líneas), Cada artículo guardado como ejemplo etiquetado para fine-tuning de un modelo dominicano, Fuentes pendientes (El Nuevo Diario, Noticias SIN, Acento vía Google News RSS, El Caribe)

### Community 140 - "Frontend Components"
Cohesion: 0.60
Nodes (5): LocalityCombobox(), closeList(), onKeyDown(), openList(), pick()

### Community 142 - "Frontend API Client"
Cohesion: 0.33
Nodes (5): components, $defs, operations, paths, webhooks

### Community 146 - "Analysis Tests"
Cohesion: 0.47
Nodes (3): apply_boost(), Ajusta las probabilidades por frase de `LocalAnalyzer` sumando `BOOST` a la…, TestApplyBoost

### Community 147 - "Analysis Tests"
Cohesion: 0.47
Nodes (3): apply_entity_relation_boost(), Como `apply_boost`, pero con el léxico relacional dirigido a entidad. Debe…, TestApplyEntityRelationBoost

### Community 148 - "API Tests"
Cohesion: 0.47
Nodes (3): `entity` y `locality` unen tablas con varias filas por artículo. Se resolvía…, SQL emitido por GET /api/articles con estos filtros., TestFiltrosQueMultiplicanFilas

### Community 149 - "DB Tests"
Cohesion: 0.33
Nodes (3): Guarda contra la regresión de empaquetado del catálogo geográfico. El JSON de…, Si el JSON se mueve fuera de `src/odin/`, ningún glob de package-data lo…, test_seed_file_lives_inside_the_installable_package()

### Community 150 - "Design Handoff"
Cohesion: 0.70
Nodes (4): buildFragment(), hexToRgb(), Plasma(), waitForOgl()

### Community 151 - "Superpowers Plans"
Cohesion: 0.50
Nodes (5): Plan: Filtros de Reportes — URL compartible, conteos por faceta, vistas guardadas, ArticleFilterParams (objeto de filtros compartido por los dos endpoints), Conteos por faceta (cada dimensión se cuenta ignorando su propio filtro), Vistas guardadas de filtros en localStorage (sin tabla saved_views), La URL como única fuente de verdad del filtrado (compartible, botón Atrás)

### Community 152 - "Frontend Dependencies"
Cohesion: 0.40
Nodes (4): name, private, type, version

### Community 153 - "Frontend Components"
Cohesion: 0.40
Nodes (3): EXISTING, mockedCreateAlias, mockedListAliases

### Community 154 - "Frontend Components"
Cohesion: 0.50
Nodes (4): AnalyzeProgress(), STAGES, stepColor(), StepState

### Community 155 - "Frontend Components"
Cohesion: 0.40
Nodes (3): LayoutProps, NAV_ITEMS, WorkspaceOutletContext

### Community 157 - "Frontend Components"
Cohesion: 0.40
Nodes (3): Nav(), NavItem, NavProps

### Community 158 - "Frontend Components"
Cohesion: 0.40
Nodes (3): ACTIVE_STYLES, Sentiment, SENTIMENTS

### Community 159 - "Frontend Components"
Cohesion: 0.40
Nodes (3): mockedCreate, mockedList, mockedReset

### Community 160 - "Frontend API Client"
Cohesion: 0.50
Nodes (5): analyzeUrl(), pollDelay(), finish(), onVisible(), pollJob()

### Community 161 - "Frontend API Client"
Cohesion: 0.40
Nodes (5): del(), deleteAlias(), deleteArticle(), deleteArticleLocality(), deleteEntity()

### Community 162 - "Scripts"
Cohesion: 0.50
Nodes (4): _golden_set_urls(), main(), Path, Estima la tasa base de sentimiento por frase de pysentimiento y la escribe a…

### Community 163 - "Analysis Tests"
Cohesion: 0.50
Nodes (3): has_negation_cue(), True si el texto trae una negación/desmentido explícito de `_NEGATION_CUES` —…, TestHasNegationCue

### Community 164 - "API Routers"
Cohesion: 0.40
Nodes (5): analyze(), BackgroundTasks, post, Response, Encola el análisis de la URL (§3.1 de task.md): la descarga y el NLP corren en…

### Community 165 - "API Routers"
Cohesion: 0.40
Nodes (5): delete_article(), delete, Borra permanentemente un artículo y sus menciones (§8.2): no hay archivado ni…, delete_article(), Borra permanentemente un artículo y sus menciones (§8.2): no hay archivado ni…

### Community 167 - "Favicon"
Cohesion: 0.83
Nodes (4): Odin Favicon, Iridescent Gradient Glow, Lightning Bolt Glyph, Odin Brand Identity

### Community 172 - "Frontend Components"
Cohesion: 0.67
Nodes (3): hexToVec3(), SoftAurora(), SoftAuroraProps

### Community 176 - "Scripts"
Cohesion: 0.67
Nodes (3): main(), Checkpoint de documentación (task.md §10.1, tarea 30). La documentación de Odin…, _staged_files()

### Community 215 - "API Routers"
Cohesion: 0.67
Nodes (3): get_job(), get, Estado/resultado de un job de POST /api/analyze. Devuelve el JSON armado a mano…

## Knowledge Gaps
- **267 isolated node(s):** `$schema`, `typescript`, `oxc`, `react/rules-of-hooks`, `warn` (+262 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1217 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **57 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `sqlite_sessionmaker()` connect `API Filter Tests` to `Entity Alias Management`, `API Tests`, `Locality API Tests`, `Localities DB Model`, `Canonicalization Tests`, `DB Test Fixtures`, `API Tests`, `API Tests`, `Article Analysis Tests`, `API Tests`, `API Tests`, `Report Repair Scripts`, `Word Export API Tests`, `Canonical Entities DB`, `User DB Model Tests`, `API Tests`, `API Tests`, `API Tests`, `API Tests`, `API Tests`, `API Tests`, `Tests`, `Canonicalization Tests`, `API Tests`, `API Tests`, `Core Tests`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `Article` connect `Report Repair Scripts` to `Documentalist Users & KPIs`, `Article Service & Schemas`, `Canonical Entities API`, `API Filter Tests`, `Locality API Tests`, `Localities DB Model`, `Analyze Service Orchestration`, `Locality Service`, `API Tests`, `Article Analysis Tests`, `API Tests`, `API Tests`, `Scripts`, `Core Pipeline & Scraping`, `Word Export API Tests`, `API Routers`, `Source Router & Scraper Tests`, `Canonical Entities DB`, `API Tests`, `API Tests`, `Alias DB & Merge Scripts`, `API Tests`, `API Tests`, `Word Export Service`, `Tests`, `API Tests`, `Core Tests`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `EntityResult` connect `Canonicalization Tests` to `Analyzer Base & Fallback`, `LLM Analyzers (Gemini/Groq)`, `Canonicalization Tests`, `Local Analyzer`, `Service Tests`, `Analyzer Evaluation Script`, `Local Analyzer & Seed`, `Local Analyzer Sentiment`, `Evaluate Script Tests`, `Core Tests`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 116 inferred relationships involving `sqlite_sessionmaker()` (e.g. with `.test_computes_person_map_when_not_provided()` and `.test_resolves_unique_surname_and_skips_ambiguous()`) actually correct?**
  _`sqlite_sessionmaker()` has 116 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `Article` (e.g. with `main()` and `main()`) actually correct?**
  _`Article` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `EntityResult` (e.g. with `_match_entities()` and `_update_metrics()`) actually correct?**
  _`EntityResult` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `LocalAnalyzer` (e.g. with `main()` and `_build_analyzer()`) actually correct?**
  _`LocalAnalyzer` has 15 INFERRED edges - model-reasoned connections that need verification._