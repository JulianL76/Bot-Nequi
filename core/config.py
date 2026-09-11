"""Configuración compartida: claves de API, modelos y rutas de datos.

Las claves se leen de variables de entorno (cargadas vía python-dotenv) igual
que en el bot original. Las rutas de archivos de estado (cuota) se resuelven de
forma absoluta para que funcionen sin importar el directorio de trabajo desde el
que se ejecute (bot o servidor Django).
"""

import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# --- Claves de API ---------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
GROQ_KEY_BACKUP = os.getenv("GROQ_API_KEY_BACKUP")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# --- Modelos ---------------------------------------------------------------
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.2-11b-vision-preview")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Proveedor que se intenta primero. Por defecto Gemini: el modelo de visión de
# Groq de arriba está dado de baja ("has been decommissioned"), así que con Groq
# primero cada imagen gastaba una subida en base64 que siempre fallaba con 400
# antes de caer al respaldo. Volver a "groq" cuando GROQ_MODEL apunte a un modelo
# vigente. El archivo preferred_ia.json (que fija el bot de Telegram) tiene
# prioridad sobre esto.
IA_PREFERIDA = os.getenv("IA_PREFERIDA", "gemini")

# --- Límites oficiales Groq free tier --------------------------------------
GROQ_RPD = 1000    # requests per day
GROQ_RPM = 30      # requests per minute
GROQ_TPD = 500000  # tokens per day

# --- Procesamiento por lotes ------------------------------------------------
# Tamaño del lote para la subida masiva (para no saturar la IA y evitar 429).
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "30"))

# --- Rutas de estado --------------------------------------------------------
# Directorio donde se guardan archivos de estado (cuota, preferencia de IA).
# Por defecto, el raíz del repo (carpeta padre de core/).
_DEFAULT_DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.getenv("NEQUI_DATA_DIR", _DEFAULT_DATA_DIR)

QUOTA_FILE = os.path.join(DATA_DIR, "quota_tracker.json")
PREFERRED_IA_FILE = os.path.join(DATA_DIR, "preferred_ia.json")
