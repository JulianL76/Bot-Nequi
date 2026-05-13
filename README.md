# Nequi OCR Telegram Bot

Este es un esqueleto de bot para Telegram que utiliza OCR (reconocimiento óptico de caracteres) para extraer datos de capturas de pantalla de Nequi.

## Requisitos

- Python 3.8 o superior.
- Una cuenta de Telegram y un Token de bot (obtenido de [@BotFather](https://t.me/BotFather)).

## Instalación

1. Clona o descarga este repositorio.
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Configura tu token de Telegram en el archivo `.env`:
   ```env
   TELEGRAM_TOKEN=tu_token_aqui
   ```

## Ejecución

Para iniciar el bot, simplemente ejecuta:
```bash
python bot.py
```

## Cómo funciona

1. Envías una foto (captura de pantalla) al bot.
2. El bot utiliza **EasyOCR** para leer el texto.
3. Se aplican **Expresiones Regulares (Regex)** para encontrar:
   - **Monto ($)**
   - **Fecha**
   - **Número de referencia o celular**
4. El bot responde con los datos extraídos en formato Markdown.

## Estructura del Proyecto

- `bot.py`: Lógica principal del bot.
- `.env`: Configuración sensible (Token).
- `requirements.txt`: Librerías necesarias.
- `temp_*.jpg`: Archivos temporales (se borran automáticamente después de procesar).
