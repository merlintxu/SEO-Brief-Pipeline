# Quick Deployment Guide

## Docker (Recommended)

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with your API keys

# 2. Deploy with helper script
chmod +x deploy.sh
./deploy.sh up

# 3. Access API
# http://localhost:8000/docs
```

## Cloud Platforms

### Railway (Easiest)
1. Push to GitHub
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variables in dashboard
4. Deploy automatically

### Render
1. Go to render.com → New Web Service
2. Connect GitHub repo
3. Add environment variables
4. Click Deploy

### AWS/GCP
See [deployment_walkthrough.md](file:///Users/marcos/.gemini/antigravity/brain/b827c405-2e97-413e-aae3-8542b4a9e3be/deployment_walkthrough.md) for detailed instructions.

## Required Environment Variables

```bash
API_KEY=your-secure-key-min-20-chars
SEMRUSH_TOKEN=your_semrush_token
SERPAPI_KEY=your_serpapi_key
OPENAI_API_KEY=your_openai_key
```

Optional but recommended:
```bash
SENTRY_DSN=your-sentry-dsn
```

## Helper Commands

```bash
./deploy.sh build    # Build Docker image
./deploy.sh up       # Start services
./deploy.sh logs     # View logs
./deploy.sh test     # Run tests
./deploy.sh down     # Stop services
```

## Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok", "active_client": null}
```
