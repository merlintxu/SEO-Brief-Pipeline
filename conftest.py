import sys
from pathlib import Path

# Add project root to sys.path so that 'seo_pipeline' package can be imported in tests
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))
