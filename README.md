# 📺 listar_youtube  
  
Pipeline automatizado que monitorea canales de YouTube, agrega los videos nuevos  
a playlists específicas y sincroniza el progreso de visualización con Google Sheets.  
La ejecución es totalmente automática mediante **GitHub Actions**.  
  
## 🚀 ¿Qué hace?  
  
- Escanea los canales configurados en una hoja de Google Sheets (`Config_Canales`).  
- Detecta subidas nuevas usando la **YouTube Data API v3** y las añade a la playlist correspondiente.  
- Escribe el estado y los metadatos de la playlist en Google Sheets (preservando fórmulas y checkboxes).  
- Envía notificaciones vía **Telegram Bot API**.  
- Persiste el estado entre ejecuciones guardando archivos JSON de vuelta en el repositorio.  
  
## 🧩 Arquitectura  
  
El proyecto sigue un patrón *controlador-motor*:  
  
- **Motor (`codigo_auto.py`):** contiene toda la lógica central (`ejecutar_playlist()`,  
  escaneo de canales, sincronización con Sheets, notificaciones y logging).  
- **Controladores:** definen la configuración de cada tipo de contenido e invocan al motor.  
  
### Tracks de contenido  
  
| Característica        | Videos diarios (`videos.py`)   | Podcasts (`podcasts.py`)        |  
| :------------------- | :----------------------------- | :------------------------------ |  
| Playlist             | `PL4wOdIekMghmXcEXaMCMtwYicoghsOg8Z` | `PL4wOdIekMghnJXO-_gOclIXiiZyPhhsxQ` |  
| Hoja destino         | `Videos`                       | `Podcasts`                      |  
| Ventana de búsqueda  | 12 horas                       | 18 horas                        |  
| Estado de revisión   | `ultima_revision_videos.json`  | `ultima_revision_podcasts.json` |  
| Estado de progreso   | `ultimo_progreso_videos.json`  | `ultimo_progreso_podcasts.json` |  
  
## 📁 Estructura del proyecto
├── .github/workflows/main.yml # Workflow de GitHub Actions (cron + dispatch)
├── codigo_auto.py # Motor central
├── videos.py # Controlador de videos diarios
├── podcasts.py # Controlador de podcasts
├── convertir_token.py # Utilidad: token.pickle -> Base64
├── ultima_revision_videos.json # Estado (high-water mark) videos
├── ultima_revision_podcasts.json # Estado (high-water mark) podcasts
├── ultimo_progreso_videos.json # Estado de progreso videos
└── ultimo_progreso_podcasts.json # Estado de progreso podcasts


## ⚙️ Configuración  
  
1. Crea credenciales OAuth en Google Cloud Console con los scopes:  
   - `https://www.googleapis.com/auth/youtube`  
   - `https://www.googleapis.com/auth/spreadsheets`  
2. Genera tu `token.pickle` localmente y conviértelo a Base64 con:  
   ```bash  
   python convertir_token.py
Configura los siguientes GitHub Secrets:


Secret	Descripción
GOOGLE_TOKEN_BASE64	Token OAuth de Google en Base64
CLIENT_SECRET_BASE64	client_secret.json en Base64
TELEGRAM_BOT_TOKEN	Token del bot de Telegram
TELEGRAM_CHAT_ID	Chat ID de destino para las notificaciones
Ajusta SPREADSHEET_ID en codigo_auto.py con el ID de tu hoja de cálculo.

▶️ Ejecución
Manual (local)

pip install google-api-python-client google-auth-oauthlib isodate requests  
python videos.py     # Procesa videos diarios  
python podcasts.py   # Procesa podcasts
Automática (GitHub Actions)
El workflow main.yml se dispara por cron (zona horaria America/Santiago):

Videos: varios bloques a lo largo del día.
Podcasts: 00:00, 12:00 y 18:00.
También admite ejecución manual (workflow_dispatch).
Tras cada ejecución, los archivos JSON de estado se commitean automáticamente al repositorio.
