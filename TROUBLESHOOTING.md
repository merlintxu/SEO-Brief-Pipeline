# Troubleshooting

This guide focuses on safe diagnosis. Do not print real `.env` values in terminals, logs, issues, PRs or docs.

## Fast Checks

```bash
git status --short --branch
python -m pip install -e ".[test]"
pytest -q
git ls-files '.env' '*__pycache__*' '*.pyc'
```

The last command should print nothing.

## API Startup

### `API_KEY environment variable must be set and >= 20 chars`

Cause: `api/main.py` validates `API_KEY` at import time.

Fix:

```bash
export API_KEY="replace_with_strong_api_key_at_least_20_chars"
uvicorn api.main:app --reload
```

On PowerShell:

```powershell
$env:API_KEY = "replace_with_strong_api_key_at_least_20_chars"
uvicorn api.main:app --reload
```

### `ModuleNotFoundError: No module named 'sentry_sdk'`

Cause: dependencies are missing or environment is stale.

Fix:

```bash
python -m pip install -e ".[test]"
```

Runtime-only fix:

```bash
python -m pip install -r requirements.txt
```

## Authentication

### `403 Invalid or missing X-API-Key header`

Cause: request header does not match `API_KEY`.

Fix:

```bash
curl -H "X-API-Key: replace_with_api_key" http://localhost:8000/health
```

`/health` is exempt from auth, but protected endpoints require the header.

## Configuration

### `No hay cliente/proyecto activo configurado`

Cause: `PipelineConfig.active_client` or `active_project` is missing.

Fix with CLI:

```bash
python client_manager.py
```

Files to inspect without printing secrets:

- `data/clients.json`
- `data/projects.json`

### JSON config does not load

Cause: malformed JSON or missing required fields.

Validate:

```bash
python -m json.tool data/clients.json > /tmp/clients.checked.json
python -m json.tool data/projects.json > /tmp/projects.checked.json
```

On Windows PowerShell, use a local temp filename instead of `/tmp/...`.

## SEMrush

### `SEMrush ERROR 122`

Cause: invalid token or plan without API access.

Fix:

- Check SEMrush dashboard token status.
- Confirm `semrush_token` is present in active client config or loaded from `.env` by the CLI.
- Do not paste the token into logs.

### `SEMrush: solo X units`

Cause: available API units are below `DEFAULT_UNITS_MIN_REQUIRED`.

Fix:

- Wait for reset or add units.
- Lower request volume (`related_limit`).
- Use cache where possible.

## SERP Providers

### `Todos los proveedores SERP fallaron (SerpAPI + DataForSEO)`

Cause: SerpAPI failed and DataForSEO fallback was unavailable or failed.

Checklist:

- Active client has `serpapi_key`, or request passes `api_key`.
- If using fallback, both `dataforseo_login` and `dataforseo_password` are configured.
- Network access is available.
- Provider quotas are not exhausted.

### DataForSEO is not called

Expected behavior if either DataForSEO credential is missing. The fallback requires both login and password.

## OpenAI

### `OpenAIError` or structured output parsing failure

Cause: invalid key, quota/rate limit, model issue, or response not matching `SEOBriefing`.

Checklist:

- Confirm active client has `openai_key`.
- Confirm account quota and model access.
- Keep `SEOBriefing` schema changes backward compatible with tests.

Current model default:

```text
gpt-4o-2024-11-20
```

## Google Search Console

### `Archivo de credenciales GSC no encontrado`

Cause: `gsc_sa_path` points to a missing service account JSON.

Fix:

- Place the service account file under `credentials/`.
- Confirm the path in `data/clients.json`.
- Ensure `credentials/` remains ignored.

### `Error calling GSC API`

Cause: missing permissions, invalid property, API disabled, or service account not added to Search Console.

Fix:

- Add the service account email to the GSC property.
- Verify `gsc_property` format, e.g. `https://example.com/` or `sc-domain:example.com`.
- Enable Search Console API in Google Cloud.

Implementation note: GSC click totals map to the `GscPage.clicks` model field. If this fails, check provider response shape first.

## Google Sheets

### `PERMISSION_DENIED`

Cause: service account does not have access to the spreadsheet.

Fix:

- Share the sheet with the service account email.
- Grant Editor access.
- Confirm `sheets_id` contains the spreadsheet id or URL expected by the code path.

### Upload skipped

Expected if any of these is false:

- request has `upload_to_sheets=true`
- active client has `sheets_sa_path`
- active project has `sheets_id`

## Outputs And Downloads

Allowed filenames are defined in `api/main.py` as `ALLOWED_FILES`.

If `GET /outputs/{run_id}/{filename}` returns `403`, the filename is not whitelisted.

If it returns `404`, check:

- `run_id` is correct.
- API status file exists under `outputs/{run_id}/status.json`.
- Pipeline artifacts may be under project output path: `{project.output_dir}/{project.project_id}/{run_id}`.

Path unification is a roadmap item.

Before deep provider debugging, read `error_category` in `status.json` and `run_metrics.json`:

- `auth`: credentials/permissions
- `quota`: exhausted plan or billing cap
- `rate_limit`: provider throttling
- `timeout`: slow upstream or network timeout
- `network`: transport/connectivity errors
- `validation`: malformed payload/config shape
- `unknown`: uncategorized runtime failure

## CI Failures

### Secret or bytecode guard fails

Cause: tracked files include forbidden local artifacts or secret-like values.

Fix:

```bash
git rm --cached .env
git rm --cached -r -- '**/__pycache__'
git rm --cached -- '*.pyc'
```

Then verify:

```bash
git ls-files '.env' '*__pycache__*' '*.pyc'
```

Do not delete local `.env` unless you have a backup.

### Tests fail only in CI

Compare install mode:

```bash
python -m pip install -e ".[test]"
pytest -q
```

CI uses editable install, not only `requirements.txt`.

## Debugging Without Leaking Secrets

Safe:

```bash
python -m json.tool data/projects.json
pytest -q tests/test_api_security.py
pytest -q tests/test_serp_io.py
```

Avoid:

```bash
cat .env
grep API_KEY .env
print(os.environ)
```

If you need to confirm a variable exists, print only its name and length, never its value.
