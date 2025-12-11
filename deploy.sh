#!/bin/bash
# deploy.sh - Production deployment script for SEO Brief Pipeline

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  SEO Brief Pipeline - Deployment Script${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please copy .env.example to .env and fill in your API keys:"
    echo "  cp .env.example .env"
    exit 1
fi

# Check required environment variables
required_vars=("API_KEY" "SEMRUSH_TOKEN" "SERPAPI_KEY" "OPENAI_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env || grep -q "^${var}=$" .env || grep -q "^${var}=your_" .env; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo -e "${YELLOW}Warning: The following environment variables are not set:${NC}"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Parse command line arguments
COMMAND=${1:-help}

case $COMMAND in
    build)
        echo -e "${GREEN}Building Docker image...${NC}"
        docker build -t seo-pipeline:latest .
        echo -e "${GREEN}✓ Build complete${NC}"
        ;;
    
    up)
        echo -e "${GREEN}Starting services with docker-compose...${NC}"
        docker-compose up -d
        echo -e "${GREEN}✓ Services started${NC}"
        echo ""
        echo "API available at: http://localhost:8000"
        echo "Swagger docs: http://localhost:8000/docs"
        echo ""
        echo "Check logs with: docker-compose logs -f"
        ;;
    
    down)
        echo -e "${YELLOW}Stopping services...${NC}"
        docker-compose down
        echo -e "${GREEN}✓ Services stopped${NC}"
        ;;
    
    restart)
        echo -e "${YELLOW}Restarting services...${NC}"
        docker-compose restart
        echo -e "${GREEN}✓ Services restarted${NC}"
        ;;
    
    logs)
        docker-compose logs -f
        ;;
    
    test)
        echo -e "${GREEN}Running tests...${NC}"
        docker-compose run --rm seo-pipeline-api pytest -v
        ;;
    
    shell)
        echo -e "${GREEN}Opening shell in container...${NC}"
        docker-compose exec seo-pipeline-api /bin/bash
        ;;
    
    clean)
        echo -e "${YELLOW}Cleaning up...${NC}"
        docker-compose down -v
        docker system prune -f
        echo -e "${GREEN}✓ Cleanup complete${NC}"
        ;;
    
    status)
        echo -e "${GREEN}Service status:${NC}"
        docker-compose ps
        ;;
    
    help|*)
        echo "Usage: ./deploy.sh [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  build    - Build Docker image"
        echo "  up       - Start services"
        echo "  down     - Stop services"
        echo "  restart  - Restart services"
        echo "  logs     - View logs (follow)"
        echo "  test     - Run tests in container"
        echo "  shell    - Open shell in container"
        echo "  status   - Show service status"
        echo "  clean    - Stop services and clean up"
        echo "  help     - Show this help"
        ;;
esac
