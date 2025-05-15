# Rasa Core - Microservicio de Chatbot

## Descripción General

Este microservicio encapsula el motor de Rasa Core, responsable del procesamiento de lenguaje natural, la gestión de diálogos y la orquestación de acciones personalizadas para el chatbot MunBot. El servicio se configura para recibir mensajes a través de la API REST, procesarlos y devolver respuestas basadas en el entrenamiento y las acciones definidas.

## Función del Microservicio

- **Procesamiento del Lenguaje Natural (NLU):** Detecta intents y extrae entidades de las conversaciones.
- **Gestión de Diálogos:** Orquesta el flujo de la conversación según las reglas, historias y políticas configuradas.
- **Integración con Acciones Personalizadas:** Llama a acciones (externas o internas) para procesar funcionalidades específicas (por ejemplo, agendar citas o registrar reclamos).

## Pasos para Construir la Imagen Docker

1. **Verifica la Estructura del Proyecto:**  
   Asegúrate de tener los siguientes elementos en la carpeta `rasa-core/`:
   - Archivos de configuración: `config.yml`, `credentials.yml`, `domain.yml`, `endpoints.yml`, `.env`
   - Datos de entrenamiento en la carpeta `data/` (incluye `nlu.yml`, `rules.yml`, `stories.yml`)
   - Código de acciones personalizadas en la carpeta `actions/` (`actions.py` y `__init__.py`)
   - (Opcional) Directorio `models/` con el modelo entrenado.

2. **Construir la Imagen Docker:**  
   Ejecuta el siguiente comando en la raíz de la carpeta `rasa-core/` (donde se encuentra el Dockerfile):

   ```bash
   docker build -t munbot-rasa-core .
