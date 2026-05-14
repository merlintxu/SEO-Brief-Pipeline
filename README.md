# SEO Brief Pipeline

Pipeline DB-first para generar briefings SEO usando datos de SEMrush, SERP real, auditoría de competidores, modelos OpenAI/Ollama/Anthropic, Google Search Console opcional y export opcional a Google Sheets.

## Documentación

- [AGENTS.md](AGENTS.md): guía principal para agentes y mantenedores.
- [Architecture](ARCHITECTURE.md): arquitectura, flujo de datos y contratos.
- [Project map](docs/PROJECT_MAP.md): relación de ficheros, funciones y artefactos.
- [External APIs](docs/EXTERNAL_APIS.md): proveedores externos, credenciales y fallos esperados.
- [Pipeline deep dive](docs/PIPELINE_DEEP_DIVE.md): análisis paso a paso, riesgos y mejoras por etapa.
- [Runtime operations](docs/RUNTIME_OPERATIONS.md): ejecución local, API, debugging y despliegue.
- [Immediate action plan](docs/IMMEDIATE_ACTION_PLAN.md): próximas acciones operativas y criterios de aceptación.
- [Improvement roadmap](docs/IMPROVEMENT_ROADMAP.md): plan priorizado de mejoras.
- [Troubleshooting](TROUBLESHOOTING.md): diagnóstico de fallos frecuentes.
- [Security](SECURITY.md): normas de credenciales e incident response.

## Capacidades

- Investigación de keywords con SEMrush.
- Análisis SERP con SerpAPI y fallback opcional a DataForSEO.
- Auditoría de URLs competidoras: title, H1, meta description, word count, headings y schema signals.
- Detección opcional de canibalización con Google Search Console.
- Generación de anchors internos y externos.
- Generación de briefing SEO con gateway de modelos y contrato Pydantic `SEOBriefing`.
- Persistencia SQLite de jobs, métricas, outputs finales y audit trail.
- Exportación a JSON, Markdown, CSV/XLSX y subida opcional a Google Sheets.
- API FastAPI con autenticación por `X-API-Key`, rate limiting y descargas por whitelist.
- Dashboard operativo `/ops` con administración de jobs y audit trail append-only para acciones de operador.
- Métricas por run con estimaciones de coste y tokens en `run_metrics.json`.
- Evaluación SLO local sobre ventanas de `run_metrics.json`.

## Instalación

Runtime simple:

```bash
python -m pip install -r requirements.txt
```

Desarrollo y tests:

```bash
python -m pip install -e ".[test]"
```

## Configuración

1. Copia el ejemplo:

```bash
cp .env.example .env
```

2. Rellena `.env` con tus valores reales. No los pegues en issues, commits, logs ni documentación.

Variables principales:

```env
SEMRUSH_TOKEN=replace_with_semrush_token
SERPAPI_KEY=replace_with_serpapi_key
OPENAI_API_KEY=replace_with_openai_key
LLM_PROVIDER=openai
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1
# ANTHROPIC_API_KEY=replace_with_anthropic_key
# ANTHROPIC_MODEL=claude-3-5-sonnet-latest
API_KEY=replace_with_strong_api_key_at_least_20_chars
DFSP_USERNAME=replace_with_dataforseo_login
DFSP_PASSWORD=replace_with_dataforseo_password
SENTRY_DSN=
```

3. Configura clientes y proyectos en:

- `data/clients.json`
- `data/projects.json`

Los service accounts de Google deben vivir en `credentials/`, que está ignorado por Git.

## Uso Rápido

CLI:

```bash
python client_manager.py
```

API:

```bash
uvicorn api.main:app --reload
```

Tests:

```bash
pytest -q
```

Cache:

```bash
python tools/cache_admin.py inspect
python tools/cache_admin.py clear --yes
```

Batch:

```bash
python tools/batch_runner.py data/batch_keywords.csv --batch-id manual_20260514
```

Gradio local:

```bash
python apps/gradio_app.py
```

## API

Todos los endpoints salvo `/health`, `/docs`, `/openapi.json` y `/redoc` requieren header:

```http
X-API-Key: replace_with_api_key
```

Crear briefing:

```bash
curl -X POST "http://localhost:8000/briefing" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace_with_api_key" \
  -d '{
    "keyword": "marketing digital",
    "target_url": null,
    "upload_to_sheets": false,
    "related_limit": 30,
    "serp_num": 10
  }'
```

Consultar estado:

```bash
curl -H "X-API-Key: replace_with_api_key" \
  "http://localhost:8000/briefing/20260508_120000"
```

Descargar artefactos:

```bash
curl -H "X-API-Key: replace_with_api_key" \
  "http://localhost:8000/outputs/20260508_120000/status.json"
```

Las descargas solo permiten nombres incluidos en la whitelist de `api/main.py`; no existe mount `/static` para exponer todo `outputs/`. Cada run también escribe `run_metrics.json` con duraciones y conteos por etapa.
El modo operativo por defecto es DB-first: `upload_to_sheets` está desactivado salvo que se solicite explícitamente.

Dashboard operativo:

```bash
curl -H "X-API-Key: replace_with_api_key" \
  "http://localhost:8000/ops/audit-trail?limit=50&cursor=0"
```

`/ops` sirve la UI operativa. El audit trail de operador se persiste mediante `GET/POST /ops/audit-trail`; el log es append-only y no guarda valores de `X-API-Key`. El detalle de jobs expone `cost_summary` cuando existe `run_metrics.json`.

SLO operativo:

```bash
curl -H "X-API-Key: replace_with_api_key" \
  "http://localhost:8000/ops/slo?limit=50"
```

La lista de jobs admite filtros operativos adicionales:

```bash
curl -H "X-API-Key: replace_with_api_key" \
  "http://localhost:8000/jobs?status=failed&error_category=network&provider=serpapi"
```

## Seguridad

- `.env`, `credentials/`, `outputs/`, `runs/`, caches y bytecode no deben versionarse.
- CI bloquea `.env`, `__pycache__`, `.pyc` y patrones de secretos en archivos trackeados.
- No imprimas valores de `.env` al depurar.
- Las claves reales se gestionan fuera del repo.

## Estado De Calidad

Comandos esperados antes de entregar cambios:

```bash
python -m pip install -e ".[test]"
pytest -q
git diff --check
git ls-files '.env' '*__pycache__*' '*.pyc'
```

El último comando debe devolver vacío.
