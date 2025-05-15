# Documentación de la Estructura y Configuración de Rasa Core

Este documento describe la estructura de archivos y la configuración utilizada en el microservicio Rasa Core. Se incluye información sobre cada componente y notas específicas para facilitar el mantenimiento y la integración.

## Estructura de Archivos

- **Dockerfile:**Contiene las instrucciones para construir la imagen Docker, incluyendo:

  - Instalación de dependencias del sistema (gcc, libssl-dev, curl).
  - Instalación de dependencias de Python a partir de `requirements.txt`.
  - Copia de archivos de configuración (`config.yml`, `credentials.yml`, `domain.yml`, `endpoints.yml`, `.env`).
  - Inclusión de datos de entrenamiento en la carpeta `data/`.
  - Inclusión de acciones personalizadas en la carpeta `actions/`.
  - Copia del directorio `models/` con el modelo entrenado.
  - Exposición del puerto 5005 y comando de inicio.
- **Archivos de Configuración:**

  - **config.yml:** Define el pipeline de NLU y otras configuraciones de Rasa.
  - **credentials.yml:** Configura los canales de comunicación, como REST y Socket.io.
  - **domain.yml:** Define intents, entities, slots, acciones y respuestas (utters) para el chatbot.
  - **endpoints.yml:** Especifica el endpoint para el servidor de acciones.
  - **.env:** Contiene variables de entorno (por ejemplo, configuraciones relacionadas con SQLAlchemy).
- **Datos de Entrenamiento:**Carpeta `data/` que incluye:

  - `nlu.yml`: Ejemplos de entrenamiento para NLU.
  - `rules.yml`: Reglas de diálogo.
  - `stories.yml`: Historias de conversación.
- **Acciones Personalizadas:**Carpeta `actions/` que contiene el código (actions.py, __init__.py) que gestiona las interacciones complejas y delega a microservicios externos según sea necesario.
- **Modelos Entrenados:**
  Directorio `models/` que contiene el modelo entrenado que Rasa utilizará al iniciar el servicio.

## Configuración de Rasa

- **Pipeline de NLU:**Definido en `config.yml`, utiliza componentes como SpacyNLP, Tokenizer, RegexFeaturizer, DIETClassifier, etc. para procesar el lenguaje natural.
- **Intents y Utters:**Definidos en `domain.yml` y `nlu.yml`. Aquí se establecen los intents del usuario y las respuestas automáticas (utters) que el chatbot entregará.
- **Acciones:**Se definen en `domain.yml` y se implementan en el archivo `actions.py` dentro de la carpeta `actions/`. La idea es mantener la orquestación en Rasa y delegar la lógica de negocio a microservicios externos.
- **Endpoints de Acciones:**
  El archivo `endpoints.yml` apunta a la URL del servidor de acciones, el cual puede estar en el mismo contenedor o ser un servicio independiente. Actualmente, se apunta a `http://localhost:5678/webhook/rasa-action`.

## Notas de Configuración y Preguntas Frecuentes

**¿Cómo actualizar el modelo entrenado?**

- Entrena el modelo localmente y copia el directorio `models/` actualizado en la imagen Docker. Reconstruye la imagen para que se incluya el nuevo modelo.

**¿Cómo se gestionan las variables de entorno?**

- El archivo `.env` se copia dentro del contenedor, pero para entornos de producción se recomienda configurar las variables en el entorno de despliegue o utilizar un gestor de secretos.

**¿Qué hacer si necesito modificar la lógica de una acción?**

- Primero refactoriza la acción para que realice una llamada a la API del microservicio correspondiente (por ejemplo, para agendar citas o registrar reclamos). De esta forma, la lógica principal se mantiene en el microservicio y Rasa solo se encarga de la orquestación.

**¿Cómo se configura la comunicación entre Rasa y otros servicios?**

- Revisa `credentials.yml` para la configuración de canales (REST, Socket.io) y `endpoints.yml` para el servidor de acciones. Asegúrate de que las URL sean accesibles desde el contenedor de Rasa.

---
