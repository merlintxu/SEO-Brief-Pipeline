# Security Best Practices for SEO Brief Pipeline

This document outlines security best practices, credential management, and incident response procedures.

## 🔐 Credential Management

### Environment Variables (.env)

**All sensitive credentials must be stored in `.env`, NOT in the codebase.**

1. **Setup**:
   ```bash
   cp .env.example .env
   # Edit .env with your real API keys
   chmod 600 .env  # (Linux/Mac) Make readable only by owner
   ```

2. **Required Variables**:
   - `SEMRUSH_TOKEN` - Semrush API token
   - `SERPAPI_KEY` - SerpAPI key
   - `OPENAI_API_KEY` - OpenAI API key
   - `API_KEY` - FastAPI authentication key (>= 20 characters)

3. **Optional Variables**:
   - `DFSP_USERNAME` / `DFSP_PASSWORD` - DataForSEO credentials
   - `PILOTERR_API_KEY` - Piloterr API key
   - `SENTRY_DSN` - Sentry error monitoring

### Automatic Loading

The pipeline uses `python-dotenv` to automatically load `.env`:

```python
# seo_pipeline/config.py
from dotenv import load_dotenv
import os

load_dotenv()  # Loads .env automatically

openai_key = os.getenv("OPENAI_API_KEY")
```

### What NOT to Do

❌ **Never hardcode API keys in source files**:
```python
# WRONG ❌
openai_key = "replace-with-a-real-key-only-in-local-env"
```

❌ **Never commit `.env` to Git**:
```bash
# Already prevented by .gitignore, but don't override it!
```

❌ **Never pass credentials as command-line arguments**:
```bash
# WRONG ❌
python client_manager.py --openai-key "replace-with-a-real-key"
```

---

## 🚨 Rotating Compromised Credentials

If any API key is exposed (accidentally committed, shared, etc.), rotate it immediately:

### 1. OpenAI API Key

1. Go to: https://platform.openai.com/account/api-keys
2. Click the **Delete** button next to the exposed key
3. Click **Create new secret key**
4. Copy the new key
5. Update `.env`:
   ```env
   OPENAI_API_KEY=replace-with-your-new-key
   ```
6. Restart the application

**Time to rotate**: < 5 minutes recommended

### 2. SerpAPI Key

1. Go to: https://serpapi.com/dashboard
2. In the API Key section, click **Regenerate**
3. Copy the new key
4. Update `.env`:
   ```env
   SERPAPI_KEY=replace-with-your-new-key
   ```
5. Restart the application

**Time to rotate**: < 5 minutes recommended

### 3. Semrush Token

1. Go to: https://www.semrush.com/user/settings/api/
2. Under "My tokens," click the token entry
3. Click **Revoke this token**
4. Generate a new token (if available in your Semrush plan)
5. Update `.env`:
   ```env
   SEMRUSH_TOKEN=replace-with-your-new-token
   ```
6. Restart the application

**Time to rotate**: < 5 minutes recommended

### 4. FastAPI Security Key

1. Generate a new secure key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Update `.env`:
   ```env
   API_KEY=replace-with-your-new-secure-key
   ```
3. Restart the API server

**Time to rotate**: Immediate (impacts all client requests)

### 5. DataForSEO Credentials

1. Go to: https://dataforseo.com/account/credentials
2. Change your password
3. Update `.env`:
   ```env
   DFSP_USERNAME=your_email@example.com
   DFSP_PASSWORD=replace-with-your-new-password
   ```
4. Restart the application

---

## 🔍 Detecting Credential Leaks

### GitHub Push Protection

GitHub automatically scans commits for exposed API keys. If you see:
```
remote: error: GH013: Repository rule violations found
remote: - GITHUB PUSH PROTECTION
remote:     Resolve the following violations before pushing again
remote:   - Push cannot contain secrets
```

**Action**:
1. Remove the exposed key from commits (see "Removing Secrets from History" below)
2. Rotate the credential immediately
3. Use `git filter-repo` to clean the history

### Manual Scan

Scan your local repository for exposed keys:

```bash
# Look for common API key field names without printing ignored local .env values.
grep -r "api.key\|api_key\|apikey" . --include="*.py" --include="*.json" --exclude-dir=.git
```

---

## 🗑️ Removing Secrets from Git History

If a secret was committed to Git, remove it from all history:

### Option 1: Using git-filter-repo (Recommended)

1. **Install**:
   ```bash
   pip install git-filter-repo
   ```

2. **Create backup branch** (safety first):
   ```bash
   git branch backup-$(date +%Y%m%d)
   ```

3. **Remove file from all commits**:
   ```bash
   git filter-repo --invert-paths --path data/clients.json
   git filter-repo --invert-paths --path .env
   ```

4. **Add remote back** (filter-repo removes it):
   ```bash
   git remote add origin [repo-url]
   ```

5. **Force push** (after verifying locally):
   ```bash
   git push origin main --force-with-lease
   ```

### Option 2: Using BFG Repo Cleaner

```bash
# Install BFG
brew install bfg  # macOS
# or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Remove sensitive files
bfg --delete-files "{.env,data/clients.json}" --no-blob-protection

# Force push
git push origin main --force-with-lease
```

---

## 🐳 Production Security

### Docker / Container Environments

**Inject credentials via environment variables, never include .env in Docker image:**

```dockerfile
# Dockerfile - DO NOT copy .env
FROM python:3.11

WORKDIR /app
COPY . .

# DON'T do this:
# COPY .env .env  ❌

RUN pip install -r requirements.txt
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0"]
```

**Pass credentials at runtime:**

```bash
# docker run
docker run -e OPENAI_API_KEY="$OPENAI_API_KEY" \
           -e SERPAPI_KEY="$SERPAPI_KEY" \
           -e API_KEY="$API_KEY" \
           seo-pipeline:latest

# docker-compose
# Set in docker-compose.yml or .env.prod (Git-ignored):
# environment:
#   OPENAI_API_KEY: ${OPENAI_API_KEY}
#   SERPAPI_KEY: ${SERPAPI_KEY}
```

### Cloud Platforms (AWS, GCP, Azure)

Use managed secret services:

- **AWS Secrets Manager**: Store secrets, retrieve via IAM roles
- **Google Cloud Secret Manager**: Native to GCP, integrated with Cloud Run
- **Azure Key Vault**: For Azure deployments
- **Heroku Config Vars**: For Heroku deployments

Example (AWS Lambda):

```python
import boto3
import json

secrets_client = boto3.client("secretsmanager", region_name="us-east-1")

def get_secret(secret_name):
    response = secrets_client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])

openai_key = get_secret("openai/api-key")
```

---

## 📋 Checklist: Post-Credential Rotation

After rotating a credential:

- [ ] Updated `.env` locally
- [ ] Verified the new key works (test API call)
- [ ] Restarted application/server
- [ ] Confirmed git history is clean (no old keys visible)
- [ ] Deleted/revoked old credential from vendor dashboard
- [ ] Informed team members (if applicable)
- [ ] Updated secrets in deployment platforms (Docker, CI/CD, Cloud)

---

## 🚀 CI/CD Security

### GitHub Actions

Never hardcode secrets in workflow files. Use GitHub Secrets:

```yaml
# .github/workflows/deploy.yml - ✅ CORRECT

name: Deploy

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      # ✅ Use GitHub Secrets, never hardcode
      - env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SERPAPI_KEY: ${{ secrets.SERPAPI_KEY }}
        run: |
          pip install -r requirements.txt
          pytest
```

---

## 📞 Incident Response

If you suspect a credential has been compromised:

1. **Immediately rotate the credential** (see "Rotating Compromised Credentials" above)
2. **Review access logs** (if available from vendor dashboards)
3. **Remove from Git history** (if committed)
4. **Notify your team** if in a collaborative environment
5. **Monitor for unusual activity** (check Sentry logs, API dashboards)

---

## ✅ Automated Scanning

Enable automated secret scanning where possible:

- **GitHub**: Secret Scanning + Push Protection (enabled by default on public repos)
- **GitLab**: Secret Detection (built-in)
- **Local**: Use `detect-secrets` or `git-secrets` as a pre-commit hook

Example with `detect-secrets`:

```bash
# Install
pip install detect-secrets

# Scan repository
detect-secrets scan --all-files

# Scan and create baseline
detect-secrets scan . > .secrets.baseline
```

---

## 📚 References

- [OWASP: Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [GitHub: Secret Scanning](https://docs.github.com/code-security/secret-scanning)
- [12-Factor App: Config](https://12factor.net/config)
- [python-dotenv Documentation](https://python-dotenv.readthedocs.io/)

---

**Last Updated**: 2025-12-11
