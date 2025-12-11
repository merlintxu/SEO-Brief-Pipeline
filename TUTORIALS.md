# SEO Brief Pipeline - Tutorials

Step-by-step guides for common use cases.

## Tutorial 1: Basic CLI Usage

### Prerequisites
- Python 3.10+ installed
- Dependencies installed (`pip install -r requirements.txt`)
- API keys configured in `.env`

### Steps

1. **Start the CLI**:
   ```bash
   python client_manager.py
   ```

2. **Create a Client**:
   - Select option `1` (Manage Clients)
   - Select `1` (Add new client)
   - Enter client details:
     - Client ID: `acme-corp`
     - Name: `ACME Corporation`
     - SEMrush Token: `your-sem rush-token`
     - SerpAPI Key: `your-serpapi-key`
     - OpenAI Key: `your-openai-key`

3. **Create a Project**:
   - Return to main menu
   - Select option `2` (Manage Projects)
   - Select `1` (Add new project)
   - Enter project details:
     - Project ID: `blog`
     - Client ID: `acme-corp`
     - Base Domain: `acmecorp.com`
     - Google Sheets ID: (optional)

4. **Set Active Context**:
   - Select option `3` (Set active client/project)
   - Choose client: `acme-corp`
   - Choose project: `blog`

5. **Run a Briefing**:
   - Select option `4` (Run briefing)
   - Enter keyword: `content marketing strategy`
   - Wait for completion (2-5 minutes)

6. **Check Results**:
   - Results are saved in `outputs/{run_id}/`
   - Files generated:
     - `briefing.json` - Structured data
     - `briefing.md` - Human-readable brief
     - `row24.xlsx` - Spreadsheet export

---

## Tutorial 2: API Integration with Python

### Create a Python Client

```python
import requests
import time
from pathlib import Path

class SEOBriefClient:
    def __init__(self, base_url="http://localhost:8000", api_key="secret-token-2025"):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}
    
    def create_briefing(self, keyword, target_url=None, upload_to_sheets=False):
        """Create a new briefing and return run_id."""
        response = requests.post(
            f"{self.base_url}/briefing",
            headers=self.headers,
            json={
                "keyword": keyword,
                "target_url": target_url,
                "upload_to_sheets": upload_to_sheets,
                "related_limit": 30,
                "serp_num": 10
            }
        )
        response.raise_for_status()
        return response.json()["run_id"]
    
    def get_status(self, run_id):
        """Get current status of a briefing."""
        response = requests.get(
            f"{self.base_url}/briefing/{run_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, run_id, timeout=300, poll_interval=5):
        """Wait for briefing to complete."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(run_id)
            
            if status["status"] == "done":
                return status
            elif status["status"] == "failed":
                raise RuntimeError(f"Briefing failed: {status.get('message')}")
            
            print(f"Status: {status.get('step', 'processing')}...")
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Briefing {run_id} did not complete within {timeout}s")
    
    def download_file(self, run_id, filename, output_path):
        """Download a generated file."""
        response = requests.get(
            f"{self.base_url}/outputs/{run_id}/{filename}",
            headers=self.headers
        )
        response.raise_for_status()
        
        Path(output_path).write_bytes(response.content)
        return output_path

# Usage Example
if __name__ == "__main__":
    client = SEOBriefClient()
    
    # Create briefing
    print("Creating briefing...")
    run_id = client.create_briefing("digital marketing trends 2025")
    print(f"Run ID: {run_id}")
    
    # Wait for completion
    print("Waiting for completion...")
    result = client.wait_for_completion(run_id)
    print(f"Status: {result['status']}")
    
    # Download results
    print("Downloading results...")
    client.download_file(run_id, "briefing.json", "output.json")
    client.download_file(run_id, "briefing.md", "output.md")
    print("Done!")
```

---

## Tutorial 3: Google Sheets Integration

### Prerequisites
- Google Cloud Project with Sheets API enabled
- Service Account with JSON key file
- Google Sheet with appropriate permissions

### Steps

1. **Create Service Account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing
   - Enable Google Sheets API
   - Create Service Account
   - Download JSON key file

2. **Configure Credentials**:
   ```bash
   mkdir -p credentials
   mv ~/Downloads/service-account.json credentials/sheets-sa.json
   ```

3. **Share Google Sheet**:
   - Open your Google Sheet
   - Click "Share"
   - Add service account email (from JSON file)
   - Grant "Editor" permissions

4. **Update Client Configuration**:
   ```bash
   python client_manager.py
   # Select client → Edit client
   # Set Sheets SA Path: credentials/sheets-sa.json
   ```

5. **Update Project Configuration**:
   ```bash
   # In CLI: Manage Projects → Edit project
   # Set Sheets ID: <spreadsheet_id_from_url>
   ```

6. **Run with Sheets Upload**:
   ```python
   response = requests.post(
       "http://localhost:8000/briefing",
       headers={"X-API-Key": "secret-token-2025"},
       json={
           "keyword": "seo best practices",
           "upload_to_sheets": True  # Enable upload
       }
   )
   ```

7. **Verify Results**:
   - Check your Google Sheet
   - New row should appear with briefing data
   - 24 columns of structured information

---

## Tutorial 4: Configuring Multiple Clients/Projects

### Use Case
Managing SEO for multiple clients with different configurations.

### YAML Configuration

**`data/clients.yml`**:
```yaml
- client_id: agency-client-1
  name: Tech Startup Inc
  semrush_token: token_1
  serpapi_key: key_1
  openai_key: openai_1
  sheets_sa_path: credentials/client1-sheets.json
  dataforseo_login: user1
  dataforseo_password: pass1

- client_id: agency-client-2
  name: E-commerce Brand
  semrush_token: token_2
  serpapi_key: key_2
  openai_key: openai_2
  sheets_sa_path: credentials/client2-sheets.json
```

**`data/projects.yml`**:
```yaml
- project_id: tech-blog
  client_id: agency-client-1
  name: Tech Blog
  base_domain: techstartup.com
  gsc_property: sc-domain:techstartup.com
  sheets_id: 1ABC...xyz
  output_dir: outputs/tech-blog

- project_id: tech-docs
  client_id: agency-client-1
  name: Documentation Site
  base_domain: docs.techstartup.com
  gsc_property: https://docs.techstartup.com/
  sheets_id: 1DEF...xyz
  output_dir: outputs/tech-docs

- project_id: ecom-blog
  client_id: agency-client-2
  name: E-commerce Blog
  base_domain: shop.example.com
  gsc_property: sc-domain:shop.example.com
  sheets_id: 1GHI...xyz
  output_dir: outputs/ecom-blog
```

### Switching Context

**Via CLI**:
```bash
python client_manager.py
# Option 3: Set active client/project
# Select client: agency-client-1
# Select project: tech-blog
```

**Via Code**:
```python
from seo_pipeline.config import get_config

config = get_config()
config.set_active_client("agency-client-1")
config.set_active_project("tech-blog")

# Now run pipeline with this context
from seo_pipeline.pipeline import run_full_pipeline
run_full_pipeline("ai automation")
```

---

## Tutorial 5: Custom Export Workflows

### Scenario: Export to Custom Database

```python
from pathlib import Path
import json
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.models import SEOBriefing

def export_to_database(briefing_path: Path):
    """Custom export function."""
    # Load briefing
    with open(briefing_path) as f:
        data = json.load(f)
    
    briefing = SEOBriefing(**data)
    
    # Example: PostgreSQL insert
    import psycopg2
    
    conn = psycopg2.connect("dbname=seo_briefs user=postgres")
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO briefings (
            keyword, meta_title, meta_description, h1, 
            tone_style, word_count, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """, (
        briefing.meta_title,
        briefing.meta_description,
        briefing.h1,
        briefing.tone_style,
        int(briefing.longitud_recomendada.split('–')[0])
    ))
    
    # Insert headings
    for section in briefing.headings:
        cursor.execute("""
            INSERT INTO briefing_sections (keyword, heading, description)
            VALUES (%s, %s, %s)
        """, (briefing.meta_title, section.heading, section.description))
    
    conn.commit()
    cursor.close()
    conn.close()

# Hook into pipeline
status_path = Path("outputs/status.json")
run_full_pipeline(
    keyword="machine learning tutorial",
    status_path=status_path,
    upload_to_sheets=False
)

# Custom export
briefing_file = Path("outputs") / "latest" / "briefing.json"
export_to_database(briefing_file)
```

### Scenario: Batch Processing

```python
import csv
from pathlib import Path
from seo_pipeline.pipeline import run_full_pipeline

def batch_process_keywords(csv_path: str, output_base: str):
    """Process multiple keywords from CSV."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            keyword = row['keyword']
            target_url = row.get('target_url')
            
            print(f"Processing: {keyword}")
            
            # Create dedicated output directory
            safe_keyword = keyword.replace(" ", "_").replace("/", "-")
            output_dir = Path(output_base) / safe_keyword
            output_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                run_full_pipeline(
                    keyword=keyword,
                    target_url=target_url,
                    status_path=output_dir / "status.json",
                    upload_to_sheets=True
                )
                print(f"✓ Completed: {keyword}")
            except Exception as e:
                print(f"✗ Failed: {keyword} - {e}")
                continue

# Usage
batch_process_keywords(
    csv_path="keywords.csv",
    output_base="outputs/batch_2025"
)
```

**`keywords.csv`**:
```csv
keyword,target_url
content marketing tips,https://example.com/blog/marketing
seo audit checklist,https://example.com/seo-guide
email campaign strategy,
```

---

## Advanced Tips

### Tip 1: Use Environment-Specific Configs
```bash
# Development
export CONFIG_ENV=dev
python client_manager.py

# Production
export CONFIG_ENV=prod
python client_manager.py
```

### Tip 2: Async Batch Processing
```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def process_keyword_async(keyword):
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as pool:
        await loop.run_in_executor(
            pool, run_full_pipeline, keyword
        )

async def main():
    keywords = ["kw1", "kw2", "kw3"]
    await asyncio.gather(*[
        process_keyword_async(kw) for kw in keywords
    ])

asyncio.run(main())
```

### Tip 3: Custom AI Models
```python
from seo_pipeline.blueprint import generate_briefing

# Use different OpenAI model
briefing = generate_briefing(
    keyword="topic",
    # ... other params
    model="gpt-4-turbo-preview",  # or "gpt-3.5-turbo"
    temperature=0.5  # Lower = more deterministic
)
```
