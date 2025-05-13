#!/bin/bash

# Verificar si Python está instalado
if command -v python3 &> /dev/null; then
    pythonVersion=$(python3 --version)
    echo "✅ Python está instalado: $pythonVersion"
else
    echo "❌ Python no está instalado. Por favor, instala Python 3.x antes de continuar."
    exit 1
fi

# Verificar si el paquete firebase-admin está instalado
echo "Comprobando si firebase-admin está instalado..."
python3 -c "import firebase_admin" 2> /dev/null

if [ $? -ne 0 ]; then
    echo "🔄 Instalando firebase-admin..."
    pip3 install firebase-admin
    if [ $? -ne 0 ]; then
        echo "❌ No se pudo instalar firebase-admin. Revisa tu conexión a internet y permisos."
        exit 1
    fi
    echo "✅ firebase-admin instalado correctamente"
else
    echo "✅ firebase-admin ya está instalado"
fi

# Ruta al script Python (relativa al script .sh)
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
script_path="$script_dir/delete_news_from_today.py"

# Verificar si el script existe
if [ ! -f "$script_path" ]; then
    echo "❌ Script Python no encontrado en: $script_path"
    exit 1
fi

# Ejecutar el script Python
echo "▶️ Ejecutando el script para eliminar noticias y grupos creados hoy..."
python3 "$script_path"

echo "✅ Ejecución del script completada"