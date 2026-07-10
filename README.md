# Prediction Scraping Bot

Este bot se ejecuta de forma automática mediante GitHub Actions, analiza fuentes de apuestas de valor y envía alertas filtradas a Telegram.

## Configuración Obligatoria (Secrets)
Para que el bot funcione sin exponer tus llaves, ve a la configuración de tu repositorio desde el navegador de tu móvil o la app:
1. Entra a **Settings** > **Secrets and variables** > **Actions**.
2. Crea un **New repository secret** con el nombre `TELEGRAM_TOKEN` (Token que te da el @BotFather).
3. Crea otro llamado `TELEGRAM_CHAT_ID` (Tu ID de usuario o el ID del canal/grupo con el signo menos `-` incluido si aplica).
