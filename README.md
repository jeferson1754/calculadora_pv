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
