#!/bin/bash
# Script para limpiar cache y reiniciar el pipeline

echo "🧹 Limpiando cache de Python..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "✅ Cache limpiado"
echo ""
echo "🚀 Iniciando Client Manager..."
echo ""

python client_manager.py
