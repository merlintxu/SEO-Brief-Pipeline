# SEO Brief Pipeline - Troubleshooting Guide

Common issues and solutions for the SEO Brief Pipeline.

## Table of Contents
1. [API Errors](#api-errors)
2. [Configuration Issues](#configuration-issues)
3. [Dependency Problems](#dependency-problems)
4. [Data Quality Issues](#data-quality-issues)
5. [Performance Problems](#performance-problems)
6. [Authentication Errors](#authentication-errors)

---

## API Errors

### SEMrush API Issues

#### Error: "SEMrush ERROR 122: clave inválida o sin acceso"
**Cause**: Invalid or expired SEMrush API key.

**Solution**:
1. Verify API key in `.env` or `clients.yml`
2. Test key directly:
   ```bash
   curl "https://api.semrush.com/?type=domain_ranks&key=YOUR_KEY&export_columns=Db&domain=semrush.com"
   ```
3. Check SEMrush dashboard for key status
4. Regenerate key if needed

#### Error: "SEMrush: solo 50 units (mínimo requerido: 100)"
**Cause**: Insufficient API units remaining.

**Solution**:
1. Check unit balance:
   ```bash
   curl "https://www.semrush.com/users/countapiunits.html?key=YOUR_KEY"
   ```
2. Options:
   - Wait for monthly reset
   - Purchase additional units
   - Reduce `related_limit` parameter
   - Adjust `min_units_required` in configuration

#### Error: "RequestException: Connection timeout"
**Cause**: Network issues or SEMrush API downtime.

**Solution**:
1. Check internet connection
2. Verify SEMrush API status: https://status.semrush.com/
3. Increase timeout in code:
   ```python
   # In semrush_io.py
   r = requests.get(BASE_URL, params=params, timeout=60)  # Increase from 30
   ```
4. Retry after waiting

---

### SerpAPI Issues

#### Error: "Todos los proveedores SERP fallaron (SerpAPI + DataForSEO)"
**Cause**: Both SERP providers failed.

**Solution**:
1. Check SerpAPI key:
   ```bash
   curl "https://serpapi.com/account?api_key=YOUR_KEY"
   ```
2. Verify quota: https://serpapi.com/dashboard
3. Configure DataForSEO as fallback:
   ```yaml
   # clients.yml
   dataforseo_login: your_login
   dataforseo_password: your_password
   ```
4. Check error logs for specific failure reason

#### Error: "SerpAPI error: Invalid API key"
**Cause**: Missing or incorrect SerpAPI key.

**Solution**:
```bash
# Verify in .env
grep SERPAPI_KEY .env

# Or in clients.yml
cat data/clients.yml | grep serpapi_key
```

---

### OpenAI Issues

#### Error: "OpenAIError: Rate limit exceeded"
**Cause**: Too many requests to OpenAI API.

**Solution**:
1. Implement exponential backoff
2. Reduce concurrent requests
3. Upgrade OpenAI plan
4. Add retry logic:
   ```python
   import time
   from openai import RateLimitError
   
   for attempt in range(3):
       try:
           briefing = generate_briefing(...)
           break
       except RateLimitError:
           wait_time = 2 ** attempt
           time.sleep(wait_time)
   ```

#### Error: "OpenAIError: Invalid API key"
**Cause**: Incorrect or expired OpenAI key.

**Solution**:
1. Verify key: https://platform.openai.com/api-keys
2. Check `.env` file:
   ```bash
   grep OPENAI_API_KEY .env
   ```
3. Regenerate key if needed

---

## Configuration Issues

### Error: "No hay cliente/proyecto activo configurado"
**Cause**: Active client or project not set.

**Solution**:
1. Via CLI:
   ```bash
   python client_manager.py
   # Option 3: Set active client/project
   ```
2. Via code:
   ```python
   from seo_pipeline.config import get_config
   
   config = get_config()
   config.set_active_client("your-client-id")
   config.set_active_project("your-project-id")
   ```
3. Verify `data/clients.yml` and `data/projects.yml` exist

### Error: "FileNotFoundError: credentials/sheets-sa.json"
**Cause**: Google Sheets service account file not found.

**Solution**:
1. Download service account JSON from Google Cloud Console
2. Place in `credentials/` directory:
   ```bash
   mkdir -p credentials
   mv ~/Downloads/service-account-*.json credentials/sheets-sa.json
   ```
3. Update `clients.yml`:
   ```yaml
   sheets_sa_path: credentials/sheets-sa.json
   ```

### Error: "ValueError: Invalid YAML syntax"
**Cause**: Malformed YAML configuration file.

**Solution**:
1. Validate YAML:
   ```bash
   python -c "import yaml; yaml.safe_load(open('data/clients.yml'))"
   ```
2. Common issues:
   - Missing colons
   - Incorrect indentation (use spaces, not tabs)
   - Unquoted special characters
3. Use YAML linter: https://www.yamllint.com/

---

## Dependency Problems

### Error: "ModuleNotFoundError: No module named 'openai'"
**Cause**: Missing dependencies.

**Solution**:
```bash
pip install -r requirements.txt
```

### Error: "ImportError: cannot import name 'SEOBriefing'"
**Cause**: Circular import or outdated code.

**Solution**:
1. Restart Python kernel/process
2. Clear `__pycache__`:
   ```bash
   find . -type d -name "__pycache__" -exec rm -r {} +
   ```
3. Reinstall in editable mode:
   ```bash
   pip install -e .
   ```

### Error: "DeprecationWarning: Pydantic max_items"
**Cause**: Using Pydantic v1 syntax with v2.

**Solution**:
Already fixed in current codebase. Update to latest version:
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

---

## Data Quality Issues

### Issue: Empty or Missing Results

#### Symptom: `keywords_secundarias` is empty
**Cause**: No related keywords found by SEMrush.

**Solution**:
1. Check if keyword exists in SEMrush database
2. Try broader keyword
3. Manually verify on SEMrush.com
4. Use alternative data source

#### Symptom: `audit_report.entries` is empty
**Cause**: All competitor URLs failed to scrape.

**Solution**:
1. Check network connectivity
2. Verify URLs are accessible
3. Some sites block scrapers - consider:
   - Using browser automation (Playwright)
   - Configuring DataForSEO scraping
   - Adding delays between requests

### Issue: Incomplete Briefing Data

#### Symptom: Missing FAQs or multimedia suggestions
**Cause**: OpenAI returned minimal response.

**Solution**:
1. Increase temperature for more creative output:
   ```python
   generate_briefing(..., temperature=0.9)
   ```
2. Use more advanced model:
   ```python
   generate_briefing(..., model="gpt-4-turbo")
   ```
3. Check prompt quality in `blueprint.py`

---

## Performance Problems

### Issue: Slow Execution (>10 minutes per keyword)

**Diagnosis**:
1. Check which step is slow:
   ```bash
   # Look at status.json during execution
   cat outputs/latest/status.json
   ```

**Solutions by Step**:

1. **SEMrush slow**:
   - Reduce `related_limit` from 60 to 30
   - Use cached results (already implemented)

2. **SERP slow**:
   - Reduce `serp_num` from 12 to 10
   - Check SerpAPI server status

3. **Audit slow**:
   - Reduce concurrent workers:
     ```python
     audit_urls(urls, max_workers=3)  # Default is 5
     ```
   - Skip heavy sites
   - Implement timeout:
     ```python
     _fetch_html(url, timeout=10)  # Reduce from 15
     ```

4. **Briefing generation slow**:
   - Use faster model: `gpt-3.5-turbo`
   - Reduce data sent to OpenAI

### Issue: High Memory Usage

**Cause**: Processing large datasets or many concurrent requests.

**Solution**:
1. Process keywords in smaller batches
2. Clear cache periodically:
   ```python
   import shutil
   shutil.rmtree('data/semrush_cache', ignore_errors=True)
   ```
3. Reduce `related_limit` and `serp_num`
4. Use generator patterns instead of loading all data at once

---

## Authentication Errors

### Google Sheets Issues

#### Error: "google.auth.exceptions.DefaultCredentialsError"
**Cause**: Service account credentials not found.

**Solution**:
1. Verify file path:
   ```bash
   ls -la credentials/sheets-sa.json
   ```
2. Check JSON format:
   ```bash
   python -c "import json; json.load(open('credentials/sheets-sa.json'))"
   ```
3. Ensure service account has Sheets API enabled

#### Error: "gspread.exceptions.APIError: PERMISSION_DENIED"
**Cause**: Service account doesn't have access to sheet.

**Solution**:
1. Share sheet with service account email (from JSON file)
2. Grant "Editor" permissions
3. Verify sheet ID is correct:
   ```python
   # Sheet ID from URL:
   # https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
   ```

### Google Search Console Issues

#### Error: "RuntimeError: Error calling GSC API"
**Cause**: GSC API authentication failure.

**Solution**:
1. Verify service account has Search Console access
2. Add service account to GSC property:
   - Go to https://search.google.com/search-console
   - Settings → Users and permissions
   - Add service account email as "Owner"
3. Wait 24-48 hours for permissions to propagate

---

## API Server Issues

### Error: "RuntimeError: Directory 'outputs' does not exist"
**Cause**: Outputs directory not created before mounting StaticFiles.

**Solution**:
Already fixed in current codebase (`api/main.py:118`). Update to latest:
```bash
git pull origin main
```

### Error: "403 Forbidden" on all API requests
**Cause**: Missing or incorrect API key.

**Solution**:
1. Include header in requests:
   ```bash
   curl -H "X-API-Key: secret-token-2025" ...
   ```
2. Set API key in environment:
   ```bash
   export API_KEY="your-custom-key"
   uvicorn api.main:app
   ```
3. Check `.env` file

---

## Debug Mode

### Enable Verbose Logging

```bash
# Set in environment
export LOG_LEVEL=DEBUG
```

```python
# Or in code
from seo_pipeline.utils.logging import logger
import logging

logger.setLevel(logging.DEBUG)
```

### Inspect Status Files

```bash
# Watch status in real-time
watch -n 2 cat outputs/latest/status.json

# View logs
tail -f logs/pipeline.log
```

### Test Components Individually

```python
# Test SEMrush
from seo_pipeline.vendors.semrush_io import SemrushClient
from pathlib import Path

client = SemrushClient(
    token="your-token",
    cache_dir=Path("data/semrush_cache")
)
results = client.fetch_related("test keyword")
print(results)

# Test SERP
from seo_pipeline.vendors.serp_io import search_raw

serp = search_raw("test keyword", api_key="your-key")
print(serp)
```

---

## Getting Help

If issues persist:

1. **Check Logs**: `logs/pipeline.log`
2. **Enable Debug Mode**: Set `LOG_LEVEL=DEBUG`
3. **Test Components**: Isolate failing component
4. **Review Changelog**: Check for known issues
5. **GitHub Issues**: Search or create new issue
6. **API Status Pages**:
   - SEMrush: https://status.semrush.com/
   - SerpAPI: https://serpapi.com/status
   - OpenAI: https://status.openai.com/

## Common Workflow Issues

### Issue: Briefing stuck at "queued" status

**Solution**:
1. Check if API server is running
2. Restart server:
   ```bash
   pkill -f "uvicorn api.main"
   uvicorn api.main:app --reload
   ```
3. Check for errors in terminal output

### Issue: Results not uploading to Google Sheets

**Checklist**:
- [ ] `upload_to_sheets: true` in request
- [ ] Service account configured
- [ ] Sheet shared with service account
- [ ] Sheets API enabled in Google Cloud
- [ ] Correct sheet ID in project config

**Verification Steps**:
1. Check service account email:
   ```bash
   cat credentials/sheets-sa.json | grep client_email
   ```
2. Verify sheet permissions:
   - Open sheet in browser
   - Click "Share"
   - Confirm service account email is listed with "Editor" access

3. Test connection:
   ```python
   import gspread
   from pathlib import Path
   
   gc = gspread.service_account(filename="credentials/sheets-sa.json")
   sh = gc.open_by_key("YOUR_SHEET_ID")
   print(f"Sheet found: {sh.title}")
   ```

4. Check logs for specific error:
   ```bash
   tail -f logs/pipeline.log | grep -i "sheet"
   ```

**Common Causes**:
- **Service account email not shared**: Add it to sheet permissions
- **Wrong sheet ID**: Verify ID from URL matches config
- **API not enabled**: Enable Google Sheets API in Google Cloud Console
- **Credentials expired**: Regenerate service account key
