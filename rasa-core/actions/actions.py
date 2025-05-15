from typing import Any, Text, Dict, List
import json
import os
import requests
import random
import string
import smtplib
from email.mime.text import MIMEText
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, EventType
from rasa_sdk.events import SlotSet
from rasa_sdk import Action
from rasa.shared.core.constants import USER_INTENT_RESTART
from rasa.core.channels.channel import UserMessage
from rasa.shared.core.events import UserUttered
from rasa.shared.core.trackers import DialogueStateTracker
from datetime import datetime
import logging
import time

# Configurar el logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Directorio base para los archivos JSON
JSON_BASE_DIR = './files/json'  # Modificado

# Rutas de los archivos JSON
HORARIOS_TRANSPORTE_PATH = os.path.join(JSON_BASE_DIR, 'horarios_transporte.json')
DOCUMENTO_REQUISITO_PATH = os.path.join(JSON_BASE_DIR, 'documento_requisito.json')
REPORTE_AEROCARRETERAS_PATH = os.path.join(JSON_BASE_DIR, 'reporte_aerocarreteras.json')
REPORTE_LINEAS_PATH = os.path.join(JSON_BASE_DIR, 'reporte_lineas.json')

# Cargar datos desde los archivos JSON
def cargar_datos_json(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except FileNotFoundError as e:
        logger.error(f"Archivo no encontrado: {ruta}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar JSON en {ruta}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error inesperado al cargar datos desde {ruta}: {e}")
        return []

# Cargar todos los datos JSON
DOCUMENTO_REQUISITO_DATA = cargar_datos_json(DOCUMENTO_REQUISITO_PATH)

class ActionSetSlotNombreDocumentoCert(Action):
    def name(self) -> Text:
        return "action_set_slot_nombre_documento_cert"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Obtener el valor de la entidad "nombre_documento_cert"
        nombre_documento = next(tracker.get_latest_entity_values("nombre_documento_cert"), None)
        
        # Si se encontró la entidad, guardarla en el slot correspondiente
        if nombre_documento:
            return [SlotSet("nombre_documento_cert", nombre_documento)]
        
        # Si no se encontró la entidad, no hacer nada
        return []
    
class ActionBuscarDocumentoPorCampo(Action):
    def name(self) -> Text:
        return "action_buscar_documento_por_campo"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        tipo_doc = tracker.get_slot("tipo_documento")
        nombre_documento = tracker.get_slot("nombre_doc_especifico")
        campo_usuario = None

        # Determinar qué campo se ha solicitado basado en el intent
        for campo in ["requisito", "ubicacion", "horario", "contacto", "telefono", "duracion", "sanciones"]:
            intent = f"proporcionar_campo_{campo}"
            if tracker.latest_message['intent'].get('name') == intent:
                campo_usuario = campo
                break

        if not nombre_documento or not campo_usuario:
            dispatcher.utter_message(text="No tengo suficiente información para realizar la búsqueda. Por favor, proporciona el nombre del documento y el campo que deseas consultar.")
            return []

        # Mapear el campo al campo en el JSON
        MAPEO_CAMPOS = {
            "requisito": "Requisitos",
            "ubicacion": "Dónde_Obtener",
            "horario": "Horario_Atencion",
            "contacto": "Correo_Electronico",
            "telefono": "Holocom_Number",
            "duracion": "tiempo_validez",
            "sanciones": "penalidad"
        }

        campo_json = MAPEO_CAMPOS.get(campo_usuario)
        if not campo_json:
            dispatcher.utter_message(text=f"No reconozco el campo '{campo_usuario}'. Por favor, elige uno válido.")
            return []

        # Buscar la información del documento específico
        documento_encontrado = next(
            (doc for doc in DOCUMENTO_REQUISITO_DATA if doc.get("Nombre_Documento", "").lower() == nombre_documento.lower()),
            None
        )

        if not documento_encontrado:
            dispatcher.utter_message(text=f"No encontré información sobre el documento '{nombre_documento}'. ¿Necesitas ayuda con algo más?")
            return []

        # Obtener la información del campo solicitado
        informacion_campo = documento_encontrado.get(campo_json, None)

        if not informacion_campo:
            dispatcher.utter_message(text=f"No encontré información sobre '{campo_json}' para el documento '{nombre_documento}'.")
            return []

        # Formatear la respuesta según el campo
        if campo_json == "Requisitos":
            requisitos = "\n".join([f"- {req}" for req in informacion_campo])
            dispatcher.utter_message(text=f"Para obtener el **{nombre_documento}**, necesitas lo siguiente:\n{requisitos}")
        elif campo_json == "Dónde_Obtener":
            dispatcher.utter_message(text=f"Puedes obtener el **{nombre_documento}** en: {informacion_campo}.")
        elif campo_json == "Horario_Atencion":
            dispatcher.utter_message(text=f"El horario de atención para obtener el **{nombre_documento}** es: {informacion_campo}.")
        elif campo_json == "Correo_Electronico":
            dispatcher.utter_message(text=f"Para consultas sobre el **{nombre_documento}**, puedes escribir al correo: {informacion_campo}.")
        elif campo_json == "Holocom_number":
            dispatcher.utter_message(text=f"Para consultas sobre el **{nombre_documento}**, puedes llamar al número: {informacion_campo}.")
        elif campo_json == "tiempo_validez":
            dispatcher.utter_message(text=f"El **{nombre_documento}** tiene una validez de: {informacion_campo}. Te recomendamos renovarlo antes de que expire.")
        elif campo_json == "penalidad":
            dispatcher.utter_message(text=f"Si no tienes el **{nombre_documento}**, {informacion_campo}. Te recomendamos obtenerlo lo antes posible para evitar problemas.")

        return []

class ActionSplitMessage(Action):
    def name(self) -> str:
        return "action_split_message"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> List[Dict[Text, Any]]:
        # Obtener el mensaje original del usuario
        text = tracker.latest_message.get('text', "")
        # Usar regex para dividir el mensaje por conectores comunes (ajusta según lo que observes en producción)
        parts = re.split(r'\s+(?:y|además|también)\s+', text, flags=re.IGNORECASE)
        
        if len(parts) > 1:
            dispatcher.utter_message(text="He detectado que has enviado varias peticiones. A continuación, procesaré cada una:")
            for idx, part in enumerate(parts, start=1):
                part = part.strip()
                if part:
                    # Aquí puedes invocar la lógica de NLU para cada parte si lo deseas.
                    # Por simplicidad, simplemente se envía un mensaje de confirmación.
                    dispatcher.utter_message(text=f"Petición {idx}: {part}")
            # En este ejemplo, no se reenvían las peticiones al NLU, pero podrías almacenar las partes en un slot o gestionar de otro modo.
        else:
            dispatcher.utter_message(text="No he detectado múltiples peticiones en tu mensaje.")
        
        return []

class ActionBuscarDocumentoPorAccion(Action):
    def name(self) -> Text:
        return "action_buscar_documento_por_accion"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Obtener la entidad accion_crd del slot
        accion_crd = tracker.get_slot("accion_crd")

        if not accion_crd:
            dispatcher.utter_message(text="No entendí el requerimiento que deseas realizar. ¿Podrías ser más específico?")
            return []

        # Cargar el archivo JSON
        try:
            with open("./files/json/documento_requisito.json", "r", encoding="utf-8") as file:
                documentos = json.load(file)
        except FileNotFoundError:
            dispatcher.utter_message(text="No se pudo encontrar la información de los documentos.")
            return []

        # Buscar el documento que corresponde a la acción
        documento_encontrado = None
        for documento in documentos:
            if isinstance(documento, dict) and any(a.lower() in accion_crd.lower() for a in documento.get("accion", [])):
                documento_encontrado = documento
                break

        if documento_encontrado:
            # Formatear los requisitos
            requisitos = "\n".join([f"- {req}" for req in documento_encontrado.get("Requisitos", [])])

            # Enviar la información del documento
            dispatcher.utter_message(
                text=f"Para {accion_crd}, necesitas el siguiente documento: {documento_encontrado['Nombre_Documento']}. Los requisitos son:\n{requisitos}\n"
                     f"Puedes solicitarlo en {documento_encontrado.get('Dónde_Obtener', 'Desconocido')}. "
                     f"El horario de atención es {documento_encontrado.get('Horario_Atencion', 'Desconocido')} y la dirección es {documento_encontrado.get('Direccion', 'Desconocido')}."
            )
        else:
            dispatcher.utter_message(text=f"No encontré un documento que corresponda a la acción '{accion_crd}'. ¿Necesitas ayuda con algo más?")

        return []

class ActionFiltrarYListar(Action):
    def name(self) -> Text:
        return "action_filtrar_y_listar"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Obtener el tipo de documento elegido (por ejemplo, "certificado", "cedula", "permiso", etc.)
        tipo_documento = tracker.get_slot("tipo_documento")
        if not tipo_documento:
            dispatcher.utter_message(text="No se ha especificado el tipo de documento.")
            return []
        
        # Filtrar los documentos en DOCUMENTO_REQUISITO_DATA según el campo "class"
        documentos_filtrados = [
            doc for doc in DOCUMENTO_REQUISITO_DATA if doc.get("class", "").lower() == tipo_documento.lower()
        ]
        if not documentos_filtrados:
            dispatcher.utter_message(text=f"No se encontraron documentos del tipo '{tipo_documento}'.")
            return []
        
        # Construir una lista formateada con el número y el nombre de cada documento filtrado
        lista_documentos = "\n".join(
            f"{doc.get('numero')}. {doc.get('Nombre_Documento')}" for doc in documentos_filtrados
        )
        
        # Preparar los mensajes a enviar
        mensaje1 = f"Entiendo que buscas un **{tipo_documento}**. Estos son los {tipo_documento}s disponibles. Puedes indicarme el nombre o número del documento que necesitas."
        mensaje2 = lista_documentos
        mensaje3 = f"¿Sobre cuál de estos {tipo_documento}s deseas información?"
        
        # Enviar los mensajes al usuario en secuencia
        dispatcher.utter_message(text=mensaje1)
        dispatcher.utter_message(text=mensaje2)
        dispatcher.utter_message(text=mensaje3)        
        return []

class ActionNormalizarDocumentoEspecifico(Action):
    def name(self) -> str:
        return "action_normalizar_documento_especifico"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> List[Dict[Text, Any]]:
        # Obtener la entrada del usuario que se quiere normalizar
        valor = tracker.get_slot("nombre_doc_especifico")
        # Obtener el tipo de documento seleccionado previamente
        tipo = tracker.get_slot("tipo_documento")
        logger.debug(f"Valor recibido: {valor}")
        logger.debug(f"Tipo de documento: {tipo}")
        
        if not valor or not tipo:
            dispatcher.utter_message(text="Falta información para normalizar el documento.")
            return []
        
        valor_lower = valor.lower().strip()
        normalized = None

        # Normalizaciones específicas (solo para el caso cuando se espera un documento, por ejemplo, "cedula")
        # Podrías también condicionar según el slot "tipo_documento", por ejemplo:
        # if tipo.lower() == "cédula":
        if "residencia" in valor_lower or "opción uno" in valor_lower or "opcion uno" in valor_lower or "opcion 1" in valor_lower or "opción 1" in valor_lower or "numero uno" in valor_lower or "número uno" in valor_lower or "numero 1" in valor_lower or "número 1" in valor_lower or valor_lower == "1" or  "residencia" in valor_lower or "definitiva" in valor_lower or "residencia definitiva" in valor_lower: normalized = "Certificado de Residencia Definitiva"
        elif "estadia" in valor_lower or  "estadía" in valor_lower or  "estadía temporal" in valor_lower or  "opción dos" in valor_lower or  "opcion dos" in valor_lower or  "opción 2" in valor_lower or  "opcion 2" in valor_lower or  "numero 2" in valor_lower or  "número 2" in valor_lower or "numero dos" in valor_lower or  "número dos" in valor_lower or valor_lower == "2": normalized = "Certificado de Estadía Temporal"
        elif "extracción" in valor_lower or  "extraccion" in valor_lower or  "extracción productiva" in valor_lower or  "extraccion productiva" in valor_lower or  "opción dos" in valor_lower or  "opcion dos" in valor_lower or "opción 3" in valor_lower or  "opcion 3" in valor_lower or "numero 3" in valor_lower or  "número 3" in valor_lower or "numero dos" in valor_lower or  "número tres" in valor_lower or  valor_lower == "3": normalized = "Certificado de Extracción Productiva"
        elif "militar" in valor_lower or  "enrolamiento militar" in valor_lower or  "enrolamiento" in valor_lower or  "opción cuatro" in valor_lower or  "opcion cuatro" in valor_lower or "opción 4" in valor_lower or  "opcion 4" in valor_lower or "numero 4" in valor_lower or  "número 4" in valor_lower or "numero cuatro" in valor_lower or  "número cuatro" in valor_lower or  valor_lower == "4": normalized = "Certificado de Enrolamiento Militar de la República"
        elif "carga" in valor_lower or "registro de carga" in valor_lower or "opción cinco" in valor_lower or  "opcion cinco" in valor_lower or "opción 5" in valor_lower or  "opcion 5" in valor_lower or "numero 5" in valor_lower or  "número 5" in valor_lower or "numero cinco" in valor_lower or  "número cinco" in valor_lower or  valor_lower == "5": normalized = "Certificado de Registro de Carga"
        elif "antecedentes" in valor_lower or  "opción seis" in valor_lower or "opcion seis" in valor_lower or "opción 6" in valor_lower or "opcion 6" in valor_lower or "numero 6" in valor_lower or  "número 6" in valor_lower or "numero seis" in valor_lower or  "número seis" in valor_lower or valor_lower == "6": normalized = "Certificado de Antecedentes"
        elif "droides" in valor_lower or "registro de droides" in valor_lower or  "opción siete" in valor_lower or  "opcion siete" in valor_lower or "opción 7" in valor_lower or  "opcion 7" in valor_lower or "numero 7" in valor_lower or  "número 7" in valor_lower or "numero siete" in valor_lower or  "número siete" in valor_lower or  valor_lower == "7": normalized = "Certificado de Registro de Droides"
        elif "licencia de piloto" in valor_lower or "piloto" in valor_lower or "piloto federado" in valor_lower or "opción ocho" in valor_lower or  "opcion ocho" in valor_lower or "opción 8" in valor_lower or  "opcion 8" in valor_lower or "numero 8" in valor_lower or  "número 8" in valor_lower or "numero ocho" in valor_lower or  "número ocho" in valor_lower or valor_lower == "8": normalized = "Licencia Oficial Piloto Federado"
        elif "licencia de transporte" in valor_lower or "transporte" in valor_lower or "transporte espacial" in valor_lower or "opción nueve" in valor_lower or  "opcion nueve" in valor_lower or "opción 9" in valor_lower or  "opcion 9" in valor_lower or "numero 9" in valor_lower or  "número 9" in valor_lower or "numero nueve" in valor_lower or  "número nueve" in valor_lower or valor_lower == "9": normalized = "Licencia de Transporte Espacial"
        elif "cédula única" in valor_lower or "cedula unica" in valor_lower or "cédula unica" in valor_lower or "cedula única" in valor_lower or "cedula unica planetaria" in valor_lower or "cédula única planetaria" in valor_lower or "cedula planetaria" in valor_lower or "cédula planetaria" in valor_lower or "opción diez" in valor_lower or  "opcion diez" in valor_lower or "opción 10" in valor_lower or  "opcion 10" in valor_lower or "numero 10" in valor_lower or  "número 10" in valor_lower or "numero diez" in valor_lower or  "número diez" in valor_lower or valor_lower == "10": normalized = "Cédula Única Sistema Planetario"
        elif "cédula bienestar" in valor_lower or "cedula bienestar" in valor_lower or "cedula de bienestar" in valor_lower or "cédula de bienestar" in valor_lower or "bienestar" in valor_lower or "opción once" in valor_lower or  "opcion once" in valor_lower or "opción 11" in valor_lower or  "opcion 11" in valor_lower or "numero 11" in valor_lower or  "número 11" in valor_lower or "numero once" in valor_lower or  "número once" in valor_lower or valor_lower == "11": normalized = "Cédula de Bienestar Social"
        elif "Exploración Planetaria" in valor_lower or "Exploracion Planetaria" in valor_lower or "cedula de Exploracion" in valor_lower or "cédula de Exploración" in valor_lower or "Exploracion" in valor_lower or "Exploración" in valor_lower or "opción doce" in valor_lower or  "opcion doce" in valor_lower or "opción 12" in valor_lower or  "opcion 12" in valor_lower or "numero 12" in valor_lower or  "número 12" in valor_lower or "numero doce" in valor_lower or  "número doce" in valor_lower or valor_lower == "12": normalized = "Permiso de Exploración Planetaria"
        elif "Asentamientos Coloniales" in valor_lower or "Asentamiento" in valor_lower or "Permiso de asentamiento" in valor_lower or "de asentamiento" in valor_lower or "Asentamiento coloniar" in valor_lower or "permiso colonial" in valor_lower or "opción trece" in valor_lower or  "opcion trece" in valor_lower or "opción 13" in valor_lower or  "opcion 13" in valor_lower or "numero 13" in valor_lower or  "número 13" in valor_lower or "numero trece" in valor_lower or  "número trece" in valor_lower or valor_lower == "13": normalized = "Permiso de Asentamientos Coloniales"
        elif "aterrizaje" in valor_lower or "de aterrizaje" in valor_lower or "opción catorce" in valor_lower or  "opcion catorce" in valor_lower or "opción 14" in valor_lower or  "opcion 14" in valor_lower or "numero 14" in valor_lower or  "número 14" in valor_lower or "numero catorce" in valor_lower or  "número catorce" in valor_lower or valor_lower == "14": normalized = "Permiso de Aterrizaje"
        elif "Comercial Intergalactica" in valor_lower or "Comercial Intergaláctica" in valor_lower or "Comercial" in valor_lower or "opción quince" in valor_lower or  "opcion quince" in valor_lower or "opción 15" in valor_lower or  "opcion 15" in valor_lower or "numero 15" in valor_lower or  "número 15" in valor_lower or "numero quince" in valor_lower or  "número quince" in valor_lower or valor_lower == "15": normalized = "Patente Comercial Intergaláctica"
        elif "inventos" in valor_lower or "de inventos" in valor_lower or "opción dieciseis" in valor_lower or  "opcion dieciseis" in valor_lower or "opción 16" in valor_lower or  "opcion 16" in valor_lower or "numero 16" in valor_lower or  "número 16" in valor_lower or "numero dieciseis" in valor_lower or  "número dieciseis" in valor_lower or valor_lower == "16": normalized = "Patente de Inventos"

        # Iterar sobre todos los documentos y filtrar solo los que coinciden con el tipo seleccionado
        for doc in DOCUMENTO_REQUISITO_DATA:
            if doc.get("class", "").lower() != tipo.lower():
                continue
            
            # Verificar si la entrada coincide exactamente con el número asignado
            if valor_lower == str(doc.get("numero", "")).lower():
                normalized = doc.get("Nombre_Documento")
                break

            # También se puede detectar si el usuario usa expresiones como "opción 3", "número 3", etc.
            if str(doc.get("numero", "")).lower() in valor_lower:
                normalized = doc.get("Nombre_Documento")
                break

            # Si no se encontró por número, verificar si la entrada contiene parte del nombre del documento
            if doc.get("Nombre_Documento", "").lower() in valor_lower:
                normalized = doc.get("Nombre_Documento")
                break

        if normalized:
            # Actualizamos el slot "nombre_doc_especifico" con el nombre completo normalizado
            dispatcher.utter_message(text=f"¿Qué información necesitas de {normalized}?")
            return [SlotSet("nombre_doc_especifico", normalized)]
        else:
            dispatcher.utter_message(text=f"No se pudo normalizar el documento: '{valor}'")
            return []

class ActionPreguntaAccionCertificado(Action):
    def name(self) -> Text:
        return "action_pregunta_accion_certificado"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Extraer las entidades "accion_cert" de la consulta
        entities = tracker.latest_message.get("entities", [])
        query_tokens = [e.get("value").lower() for e in entities if e.get("entity") == "accion_cert"]
        if not query_tokens:
            dispatcher.utter_message(text="No se han detectado palabras clave de acción en tu consulta.")
            return []

        # Filtrado general: candidatos cuyos campos "accion" contengan al menos un token de la consulta
        candidatos = []
        for certificado in DOCUMENTO_REQUISITO_DATA:
            acciones_cert = [accion.lower() for accion in certificado.get("accion", [])]
            if any(token in acciones_cert for token in query_tokens):
                candidatos.append(certificado)

        if not candidatos:
            dispatcher.utter_message(text="No se encontró ningún certificado relacionado con esa acción.")
            return []

        # Diccionarios de tokens y combinaciones prioritarias por certificado
        priority_tokens = {
            "CRD-001": ["vivo", "residencia", "domicilio", "acreditar", "certificar", "residencia", "ciudadanía", "ciudadania", "nacional", "nacionalidad"],
            "CPF-002": ["manejar", "pilotar", "volar", "conducir", "caza", "nave", "nave de asalto", "bombardero", "nave espacial"],
            "LTE-003": ["operar", "transportar", "nave de construcción", "nave de construcción", "nave de minería", "nave de transporte", "nave de pasajeros", "nave de rescate", "destructor", "carguero", "transporte", "transporte de carga", "transporte de pasajeros", "nave de carga", "vehículo de carga"],
            "ISP-005": ["renovar", "sacar", "obtener", "solictar", "renovación", "carné", "carné de identidad", "documento de identidad", "documento de identificación", "cédula de identidad", "tarjeta de identificación"],
            "CET-008": ["visitar", "ingresar", "turistear", "alojarme", "conocer", "recorrer"],
            "PEP-009": ["explorar", "investigar", "descubrir", "recorrer", "colonizar", "buscar", "hacer", "salir a explorar"],
            "RAS-010": ["colonizar", "asentar", "establecer", "crear", "fundar", "organizar"],
            "CEP-011": ["dedicarme", "extraer", "minar", "explotar", "producir", "obtener", "desarrollar", "recolectar"],
            "PCI-012": ["comerciar", "negociar", "vender", "fundar", "exportar", "importar", "establecer", "emprender", "comercializar"],
            "CEM-013": ["servicio militar", "hice", "enrolé", "serví", "alisté"],
            "CRC-014": ["registrar", "documentar", "certificar", "validar", "gestionar", "inscribir", "inventariar", "listar"],
            "CBS-015": ["acceder", "recibir", "participar", "certificar", "inscribirme", "registrarme", "registrarse", "registrar", "solicitar", "obtener"],
            "RIV-016": ["registrar", "inscribir", "patentar", "proteger", "legalizar", "formalizar"],
            "RDD-016": ["registrar", "inscribir", "certificar"],
            "PAT-018": ["aterrizar", "desembarcar", "descender", "ingresar", "autorizar", "permitir"],
            "CAT-019": ["verificar", "consultar", "revisar", "comprobar"],
        }
        priority_combinations = {
            "CRD-001": [("demostrar", "domicilio"), ("demostrar", "residencia"), ("demostrar", "ciudadania"), ("demostrar", "ciudadanía"), ("demostrar", "nacional"), ("demostrar", "nacionalidad"), ("demostrar", "ciudadano"), ("demostrar", "vivo"), ("demuestro", "domicilio"), ("demuestro", "residencia"), ("demuestro", "ciudadania"), ("demuestro", "ciudadanía"), ("demuestro", "nacional"), ("demuestro", "nacionalidad"), ("demuestro", "ciudadano"), ("demuestro", "vivo"), ("acreditar", "domicilio"), ("acreditar", "residencia"), ("acreditar", "ciudadania"), ("acreditar", "ciudadanía"), ("acreditar", "nacional"), ("acreditar", "nacionalidad"), ("acreditar", "ciudadano"), ("acreditar", "vivo"), ("acredito", "domicilio"), ("acredito", "residencia"), ("acredito", "ciudadania"), ("acredito", "ciudadanía"), ("acredito", "nacional"), ("acredito", "nacionalidad"), ("acredito", "ciudadano"), ("acredito", "vivo"), ("comprobar", "domicilio"), ("comprobar", "residencia"), ("comprobar", "ciudadania"), ("comprobar", "ciudadanía"), ("comprobar", "nacional"), ("comprobar", "nacionalidad"), ("comprobar", "ciudadano"), ("comprobar", "vivo"), ("compruebo", "domicilio"), ("compruebo", "residencia"), ("compruebo", "ciudadania"), ("compruebo", "ciudadanía"), ("compruebo", "nacional"), ("compruebo", "nacionalidad"), ("compruebo", "ciudadano"), ("compruebo", "vivo"), ("certificar", "domicilio"), ("certificar", "residencia"), ("certificar", "ciudadania"), ("certificar", "ciudadanía"), ("certificar", "nacional"), ("certificar", "nacionalidad"), ("certificar", "ciudadano"), ("certificar", "vivo"), ("certifico", "domicilio"), ("certifico", "residencia"), ("certifico", "ciudadania"), ("certifico", "ciudadanía"), ("certifico", "nacional"), ("certifico", "nacionalidad"), ("certifico", "ciudadano"), ("certifico", "vivo")],
            "CPF-002": [("manejar", "caza"), ("manejar", "caza estelar"), ("manejar", "nave"), ("manejar", "nave de asalto"), ("manejar", "nave particular"), ("manejar", "nave de superficie"), ("manejar", "nave espacial"), ("manejar", "bombardero"), ("manejar", "X-wing"), ("manejar", "A-wing"), ("manejar", "N-1 Starfighter"), ("manejar", "Millennium Falcon"), ("manejar", "U-wing"), ("manejar", "Patrol transport"), ("pilotar", "caza"), ("pilotar", "caza estelar"), ("pilotar", "nave"), ("pilotar", "nave de asalto"), ("pilotar", "nave particular"), ("pilotar", "nave de superficie"), ("pilotar", "nave espacial"), ("pilotar", "bombardero"), ("pilotar", "X-wing"), ("pilotar", "A-wing"), ("pilotar", "N-1 Starfighter"), ("pilotar", "Millennium Falcon"), ("pilotar", "U-wing"), ("pilotar", "Patrol transport"), ("volar", "caza"), ("volar", "caza estelar"), ("volar", "nave"), ("volar", "nave de asalto"), ("volar", "nave particular"), ("volar", "nave de superficie"), ("volar", "nave espacial"), ("volar", "bombardero"), ("volar", "X-wing"), ("volar", "A-wing"), ("volar", "N-1 Starfighter"), ("volar", "Millennium Falcon"), ("volar", "U-wing"), ("volar", "Patrol transport"), ("conducir", "caza"), ("conducir", "caza estelar"), ("conducir", "nave"), ("conducir", "nave de asalto"), ("conducir", "nave particular"), ("conducir", "nave de superficie"), ("conducir", "nave espacial"), ("conducir", "bombardero"), ("conducir", "X-wing"), ("conducir", "A-wing"), ("conducir", "N-1 Starfighter"), ("conducir", "Millennium Falcon"), ("conducir", "U-wing"), ("conducir", "Patrol transport")],
            "LTE-003": [("manejar", "nave de construcción"), ("manejar", "nave de minería"), ("manejar", "nave de transporte"), ("manejar", "nave de comando"), ("manejar", "nave de pasajeros"), ("manejar", "nave de rescate"), ("manejar", "destructor"), ("manejar", "carguero"), ("manejar", "transporte de carga"), ("manejar", "transporte de pasajeros"), ("manejar", "nave de carga"), ("manejar", "vehículo de carga"), ("pilotar", "nave de construcción"), ("pilotar", "nave de minería"), ("pilotar", "nave de transporte"), ("pilotar", "nave de comando"), ("pilotar", "nave de pasajeros"), ("pilotar", "nave de rescate"), ("pilotar", "destructor"), ("pilotar", "carguero"), ("pilotar", "transporte de carga"), ("pilotar", "transporte de pasajeros"), ("pilotar", "nave de carga"), ("pilotar", "vehículo de carga"), ("volar", "nave de construcción"), ("volar", "nave de minería"), ("volar", "nave de transporte"), ("volar", "nave de comando"), ("volar", "nave de pasajeros"), ("volar", "nave de rescate"), ("volar", "destructor"), ("volar", "carguero"), ("volar", "transporte de carga"), ("volar", "transporte de pasajeros"), ("volar", "nave de carga"), ("volar", "vehículo de carga"), ("conducir", "nave de construcción"), ("conducir", "nave de minería"), ("conducir", "nave de transporte"), ("conducir", "nave de comando"), ("conducir", "nave de pasajeros"), ("conducir", "nave de rescate"), ("conducir", "destructor"), ("conducir", "carguero"), ("conducir", "transporte de carga"), ("conducir", "transporte de pasajeros"), ("conducir", "nave de carga"), ("conducir", "vehículo de carga"), ("operar", "nave de construcción"), ("operar", "nave de minería"), ("operar", "nave de transporte"), ("operar", "nave de comando"), ("operar", "nave de pasajeros"), ("operar", "nave de rescate"), ("operar", "destructor"), ("operar", "carguero"), ("operar", "transporte de carga"), ("operar", "transporte de pasajeros"), ("operar", "nave de carga"), ("operar", "vehículo de carga"), ("transportar", "nave de construcción"), ("transportar", "nave de minería"), ("transportar", "nave de transporte"), ("transportar", "nave de comando"), ("transportar", "nave de pasajeros"), ("transportar", "nave de rescate"), ("transportar", "destructor"), ("transportar", "carguero"), ("transportar", "transporte de carga"), ("transportar", "transporte de pasajeros"), ("transportar", "nave de carga"), ("transportar", "vehículo de carga")],
            "ISP-005": [("renovar", "carné"), ("renovar", "carné de identidad"), ("renovar", "documento de identidad"), ("renovar", "documento de identificación"), ("renovar", "cédula de identidad"), ("renovar", "tarjeta de identificación"), ("sacar", "carné"), ("sacar", "carné de identidad"), ("sacar", "documento de identidad"), ("sacar", "documento de identificación"), ("sacar", "cédula de identidad"), ("sacar", "tarjeta de identificación"), ("obtener", "carné"), ("obtener", "carné de identidad"), ("obtener", "documento de identidad"), ("obtener", "documento de identificación"), ("obtener", "cédula de identidad"), ("obtener", "tarjeta de identificación"), ("actualizar", "carné"), ("actualizar", "carné de identidad"), ("actualizar", "documento de identidad"), ("actualizar", "documento de identificación"), ("actualizar", "cédula de identidad"), ("actualizar", "tarjeta de identificación"), ("solictar", "carné"), ("solictar", "carné de identidad"), ("solictar", "documento de identidad"), ("solictar", "documento de identificación"), ("solictar", "cédula de identidad"), ("solictar", "tarjeta de identificación"), ("renovación", "carné"), ("renovación", "carné de identidad"), ("renovación", "documento de identidad"), ("renovación", "documento de identificación"), ("renovación", "cédula de identidad"), ("renovación", "tarjeta de identificación")],
            "CET-008": [("visitar", "Curoscant"), ("visitar", "planeta"), ("visitar", "turista"), ("entrar", "Curoscant"), ("entrar", "planeta"), ("entrar", "turista"), ("ingresar", "Curoscant"), ("ingresar", "planeta"), ("ingresar", "turista"), ("turistear", "Curoscant"), ("turistear", "planeta"), ("turistear", "turista"), ("viajar", "Curoscant"), ("viajar", "planeta"), ("viajar", "turista"), ("alojar", "Curoscant"), ("alojar", "planeta"), ("alojar", "turista"), ("alojarme", "Curoscant"), ("alojarme", "planeta"), ("alojarme", "turista"), ("hospedar", "Curoscant"), ("hospedar", "planeta"), ("hospedar", "turista"), ("hospedarme ", "Curoscant"), ("hospedarme ", "planeta"), ("hospedarme ", "turista"), ("conocer", "Curoscant"), ("conocer", "planeta"), ("conocer", "turista"), ("recorrer", "Curoscant"), ("recorrer", "planeta"), ("recorrer", "turista")],
            "PEP-009": [("explorar", "territorios inexplorados"), ("explorar", "territorios desconocidos"), ("explorar", "territorios"), ("explorar", "minas"), ("explorar", "Exploración científica"), ("explorar", "Exploración minera"), ("explorar", "Exploración espacial"), ("investigar", "territorios inexplorados"), ("investigar", "territorios desconocidos"), ("investigar", "territorios"), ("investigar", "minas"), ("investigar", "Exploración científica"), ("investigar", "Exploración minera"), ("investigar", "Exploración espacial"), ("descubrir", "territorios inexplorados"), ("descubrir", "territorios desconocidos"), ("descubrir", "territorios"), ("descubrir", "minas"), ("descubrir", "Exploración científica"), ("descubrir", "Exploración minera"), ("descubrir", "Exploración espacial"), ("recorrer", "territorios inexplorados"), ("recorrer", "territorios desconocidos"), ("recorrer", "territorios"), ("recorrer", "minas"), ("recorrer", "Exploración científica"), ("recorrer", "Exploración minera"), ("recorrer", "Exploración espacial"), ("colonizar", "territorios inexplorados"), ("colonizar", "territorios desconocidos"), ("colonizar", "territorios"), ("colonizar", "minas"), ("colonizar", "Exploración científica"), ("colonizar", "Exploración minera"), ("colonizar", "Exploración espacial"), ("salir a explorar", "territorios inexplorados"), ("salir a explorar", "territorios desconocidos"), ("salir a explorar", "territorios"), ("salir a explorar", "minas"), ("salir a explorar", "Exploración científica"), ("salir a explorar", "Exploración minera"), ("salir a explorar", "Exploración espacial")],
            "RAS-010": [("colonizar", "asentamiento"), ("colonizar", "comunidad"), ("colonizar", "comunidad planetaria"), ("colonizar", "territorio en otro planeta"), ("asentar", "colonia"), ("asentar", "asentamiento"), ("asentar", "comunidad"), ("asentar", "comunidad planetaria"), ("asentar", "territorio en otro planeta"), ("establecer", "colonia"), ("establecer", "asentamiento"), ("establecer", "comunidad"), ("establecer", "comunidad planetaria"), ("establecer", "territorio en otro planeta"), ("crear", "colonia"), ("crear", "asentamiento"), ("crear", "comunidad"), ("crear", "comunidad planetaria"), ("crear", "territorio en otro planeta"), ("fundar", "colonia"), ("fundar", "asentamiento"), ("fundar", "comunidad"), ("fundar", "comunidad planetaria"), ("fundar", "territorio en otro planeta")],
            "CEP-011": [("dedicarme", "obtención", "recursos"), ("dedicarme", "extracción", "recursos"), ("dedicarme", "explotación", "recursos"), ("dedicarme", "producción", "recursos"), ("dedicarme", "perforación", "recursos"), ("dedicarme", "obtención", "materias primas"), ("dedicarme", "extracción", "materias primas"), ("dedicarme", "explotación", "materias primas"), ("dedicarme", "producción", "materias primas"), ("dedicarme", "perforación", "materias primas"), ("dedicarme", "obtención", "minerales"), ("dedicarme", "extracción", "minerales"), ("dedicarme", "explotación", "minerales"), ("dedicarme", "producción", "minerales"), ("dedicarme", "perforación", "minerales"), ("dedicarme", "obtención", "recursos naturales"), ("dedicarme", "extracción", "recursos naturales"), ("dedicarme", "explotación", "recursos naturales"), ("dedicarme", "producción", "recursos naturales"), ("dedicarme", "perforación", "recursos naturales"), ("extraer", "recursos"), ("extraer", "materias primas"), ("extraer", "recolectar"), ("extraer", "minerales"), ("extraer", "recursos naturales"), ("minar", "recursos"), ("minar", "materias primas"), ("minar", "recolectar"), ("minar", "minerales"), ("minar", "recursos naturales"), ("explotar", "recursos"), ("explotar", "materias primas"), ("explotar", "recolectar"), ("explotar", "minerales"), ("explotar", "recursos naturales"), ("producir", "recursos"), ("producir", "materias primas"), ("producir", "recolectar"), ("producir", "minerales"), ("producir", "recursos naturales"), ("obtener", "recursos"), ("obtener", "materias primas"), ("obtener", "recolectar"), ("obtener", "minerales"), ("obtener", "recursos naturales"), ("recolectar", "recursos"), ("recolectar", "materias primas"), ("recolectar", "recolectar"), ("recolectar", "minerales"), ("recolectar", "recursos naturales")],
            "PCI-012": [("comerciar", "mercaderías"), ("comerciar", "productos"), ("comerciar", "bienes"), ("comerciar", "servicios"), ("negociar", "mercaderías"), ("negociar", "productos"), ("negociar", "bienes"), ("negociar", "servicios"), ("vender", "mercaderías"), ("vender", "productos"), ("vender", "bienes"), ("vender", "servicios"), ("fundar", "empresa"), ("fundar", "negocio"), ("exportar", "productos"), ("exportar", "bienes"), ("exportar", "servicios"), ("importar", "mercaderías"), ("importar", "productos"), ("importar", "bienes"), ("importar", "servicios"), ("comerciar", "mercaderías"), ("comerciar", "productos"), ("comerciar", "bienes"), ("comerciar", "servicios"), ("establecer", "empresa"), ("establecer", "negocio"), ("establecer", "comercio"), ("establecer", "sucursal"), ("establecer", "tienda"), ("establecer", "local"), ("establecer", "punto de venta"), ("establecer", "comercio electrónico"), ("establecer", "comercio internacional"), ("establecer", "comercio interplanetario"), ("establecer", "comercio galáctico"), ("establecer", "comercio intergaláctico"), ("emprender", "empresa"), ("emprender", "negocio"), ("emprender", "comercio"), ("emprender", "sucursal"), ("emprender", "tienda"), ("emprender", "local"), ("emprender", "punto de venta"), ("emprender", "comercio electrónico"), ("emprender", "comercio internacional"), ("emprender", "comercio interplanetario"), ("emprender", "comercio galáctico"), ("emprender", "comercio intergaláctico"), ("comercializar", "mercaderías"), ("comercializar", "productos"), ("comercializar", "bienes"), ("comercializar", "servicios")],
            "CEM-013": [("demostrar", "servicio militar"), ("demostrar", "fuerzas militares"), ("demostrar", "fuerzas armadas"), ("demostrar", "militar"), ("demostrar", "fuerza armada"), ("demostrar", "milicia"), ("demostrar", "combate"), ("demostrar", "fuerza jedi"), ("acreditar", "servicio militar"), ("acreditar", "fuerzas militares"), ("acreditar", "fuerzas armadas"), ("acreditar", "militar"), ("acreditar", "fuerza armada"), ("acreditar", "milicia"), ("acreditar", "combate"), ("acreditar", "fuerza jedi"), ("comprobar", "servicio militar"), ("comprobar", "fuerzas militares"), ("comprobar", "fuerzas armadas"), ("comprobar", "militar"), ("comprobar", "fuerza armada"), ("comprobar", "milicia"), ("comprobar", "combate"), ("comprobar", "fuerza jedi"), ("compruebo", "servicio militar"), ("compruebo", "fuerzas militares"), ("compruebo", "fuerzas armadas"), ("compruebo", "militar"), ("compruebo", "fuerza armada"), ("compruebo", "milicia"), ("compruebo", "combate"), ("compruebo", "fuerza jedi"), ("validar", "servicio militar"), ("validar", "fuerzas militares"), ("validar", "fuerzas armadas"), ("validar", "militar"), ("validar", "fuerza armada"), ("validar", "milicia"), ("validar", "combate"), ("validar", "fuerza jedi"), ("confirmar", "servicio militar"), ("confirmar", "fuerzas militares"), ("confirmar", "fuerzas armadas"), ("confirmar", "militar"), ("confirmar", "fuerza armada"), ("confirmar", "milicia"), ("confirmar", "combate"), ("confirmar", "fuerza jedi"), ("certificar", "servicio militar"), ("certificar", "fuerzas militares"), ("certificar", "fuerzas armadas"), ("certificar", "militar"), ("certificar", "fuerza armada"), ("certificar", "milicia"), ("certificar", "combate"), ("certificar", "fuerza jedi"), ("pertenecí", "servicio militar"), ("pertenecí", "fuerzas militares"), ("pertenecí", "fuerzas armadas"), ("pertenecí", "militar"), ("pertenecí", "fuerza armada"), ("pertenecí", "milicia"), ("pertenecí", "combate"), ("pertenecí", "fuerza jedi"), ("participé", "servicio militar"), ("participé", "fuerzas militares"), ("participé", "fuerzas armadas"), ("participé", "militar"), ("participé", "fuerza armada"), ("participé", "milicia"), ("participé", "combate"), ("participé", "fuerza jedi"), ("serví", "servicio militar"), ("serví", "fuerzas militares"), ("serví", "fuerzas armadas"), ("serví", "militar"), ("serví", "fuerza armada"), ("serví", "milicia"), ("serví", "combate"), ("serví", "fuerza jedi"), ("enrolé", "servicio militar"), ("enrolé", "fuerzas militares"), ("enrolé", "fuerzas armadas"), ("enrolé", "militar"), ("enrolé", "fuerza armada"), ("enrolé", "milicia"), ("enrolé", "combate"), ("enrolé", "fuerza jedi"), ("enrolado", "servicio militar"), ("enrolado", "fuerzas militares"), ("enrolado", "fuerzas armadas"), ("enrolado", "militar"), ("enrolado", "fuerza armada"), ("enrolado", "milicia"), ("enrolado", "combate"), ("enrolado", "fuerza jedi"), ("alisté", "servicio militar"), ("alisté", "fuerzas militares"), ("alisté", "fuerzas armadas"), ("alisté", "militar"), ("alisté", "fuerza armada"), ("alisté", "milicia"), ("alisté", "combate"), ("alisté", "fuerza jedi"), ("alistado", "servicio militar"), ("alistado", "fuerzas militares"), ("alistado", "fuerzas armadas"), ("alistado", "militar"), ("alistado", "fuerza armada"), ("alistado", "milicia"), ("alistado", "combate"), ("alistado", "fuerza jedi"), ("hice", "servicio militar"), ("hice", "fuerzas militares"), ("hice", "fuerzas armadas")],
            "CRC-014": [("registrar", "carga"), ("registrar", "mercancía"), ("registrar", "embarque"), ("registrar", "productos"), ("registrar", "bienes"), ("registrar", "materiales"), ("registrar", "artículos"), ("registrar", "materias primas"), ("registrar", "materias"), ("registrar", "suminisitros"), ("registrar", "mercancía comercial"), ("registrar", "producto comercial"), ("registrar", "bienes comerciales"), ("registrar", "bienes de consumo"), ("registrar", "artículos de consumo"), ("documentar", "carga"), ("documentar", "mercancía"), ("documentar", "embarque"), ("documentar", "productos"), ("documentar", "bienes"), ("documentar", "materiales"), ("documentar", "artículos"), ("documentar", "materias primas"), ("documentar", "materias"), ("documentar", "suminisitros"), ("documentar", "mercancía comercial"), ("documentar", "producto comercial"), ("documentar", "bienes comerciales"), ("documentar", "bienes de consumo"), ("documentar", "artículos de consumo"), ("certificar", "carga"), ("certificar", "mercancía"), ("certificar", "embarque"), ("certificar", "productos"), ("certificar", "bienes"), ("certificar", "materiales"), ("certificar", "artículos"), ("certificar", "materias primas"), ("certificar", "materias"), ("certificar", "suminisitros"), ("certificar", "mercancía comercial"), ("certificar", "producto comercial"), ("certificar", "bienes comerciales"), ("certificar", "bienes de consumo"), ("certificar", "artículos de consumo"), ("validar", "carga"), ("validar", "mercancía"), ("validar", "embarque"), ("validar", "productos"), ("validar", "bienes"), ("validar", "materiales"), ("validar", "artículos"), ("validar", "materias primas"), ("validar", "materias"), ("validar", "suminisitros"), ("validar", "mercancía comercial"), ("validar", "producto comercial"), ("validar", "bienes comerciales"), ("validar", "bienes de consumo"), ("validar", "artículos de consumo"), ("gestionar", "carga"), ("gestionar", "mercancía"), ("gestionar", "embarque"), ("gestionar", "productos"), ("gestionar", "bienes"), ("gestionar", "materiales"), ("gestionar", "artículos"), ("gestionar", "materias primas"), ("gestionar", "materias"), ("gestionar", "suminisitros"), ("gestionar", "mercancía comercial"), ("gestionar", "producto comercial"), ("gestionar", "bienes comerciales"), ("gestionar", "bienes de consumo"), ("gestionar", "artículos de consumo"), ("inscribir", "carga"), ("inscribir", "mercancía"), ("inscribir", "embarque"), ("inscribir", "productos"), ("inscribir", "bienes"), ("inscribir", "materiales"), ("inscribir", "artículos"), ("inscribir", "materias primas"), ("inscribir", "materias"), ("inscribir", "suminisitros"), ("inscribir", "mercancía comercial"), ("inscribir", "producto comercial"), ("inscribir", "bienes comerciales"), ("inscribir", "bienes de consumo"), ("inscribir", "artículos de consumo"), ("inventariar", "carga"), ("inventariar", "mercancía"), ("inventariar", "embarque"), ("inventariar", "productos"), ("inventariar", "bienes"), ("inventariar", "materiales"), ("inventariar", "artículos"), ("inventariar", "materias primas"), ("inventariar", "materias"), ("inventariar", "suminisitros"), ("inventariar", "mercancía comercial"), ("inventariar", "producto comercial"), ("inventariar", "bienes comerciales"), ("inventariar", "bienes de consumo"), ("inventariar", "artículos de consumo")],
            "CBS-015": [("acceder", "subsidio"), ("acceder", "programa social"), ("acceder", "programas sociales"), ("acceder", "sistema de bienestar"), ("acceder", "ayuda"), ("acceder", "ayuda social"), ("acceder", "beneficios sociales"), ("acceder", "beneficio social"), ("recibir", "subsidio"), ("recibir", "programa social"), ("recibir", "programas sociales"), ("recibir", "sistema de bienestar"), ("recibir", "ayuda"), ("recibir", "ayuda social"), ("recibir", "beneficios sociales"), ("recibir", "beneficio social"), ("participar", "subsidio"), ("participar", "programa social"), ("participar", "programas sociales"), ("participar", "sistema de bienestar"), ("participar", "ayuda"), ("participar", "ayuda social"), ("participar", "beneficios sociales"), ("participar", "beneficio social"), ("certificar", "subsidio"), ("certificar", "programa social"), ("certificar", "programas sociales"), ("certificar", "sistema de bienestar"), ("certificar", "ayuda"), ("certificar", "ayuda social"), ("certificar", "beneficios sociales"), ("certificar", "beneficio social"), ("inscribirme", "subsidio"), ("inscribirme", "programa social"), ("inscribirme", "programas sociales"), ("inscribirme", "sistema de bienestar"), ("inscribirme", "ayuda"), ("inscribirme", "ayuda social"), ("inscribirme", "beneficios sociales"), ("inscribirme", "beneficio social"), ("registrarme", "subsidio"), ("registrarme", "programa social"), ("registrarme", "programas sociales"), ("registrarme", "sistema de bienestar"), ("registrarme", "ayuda"), ("registrarme", "ayuda social"), ("registrarme", "beneficios sociales"), ("registrarme", "beneficio social"), ("registrarse", "subsidio"), ("registrarse", "programa social"), ("registrarse", "programas sociales"), ("registrarse", "sistema de bienestar"), ("registrarse", "ayuda"), ("registrarse", "ayuda social"), ("registrarse", "beneficios sociales"), ("registrarse", "beneficio social"), ("registrar", "subsidio"), ("registrar", "programa social"), ("registrar", "programas sociales"), ("registrar", "sistema de bienestar"), ("registrar", "ayuda"), ("registrar", "ayuda social"), ("registrar", "beneficios sociales"), ("registrar", "beneficio social"), ("solicitar", "subsidio"), ("solicitar", "programa social"), ("solicitar", "programas sociales"), ("solicitar", "sistema de bienestar"), ("solicitar", "ayuda"), ("solicitar", "ayuda social"), ("solicitar", "beneficios sociales"), ("solicitar", "beneficio social"), ("obtener", "subsidio"), ("obtener", "programa social"), ("obtener", "programas sociales"), ("obtener", "sistema de bienestar"), ("obtener", "ayuda"), ("obtener", "ayuda social"), ("obtener", "beneficios sociales"), ("obtener", "beneficio social")],
            "RIV-016": [("registrar", "invento"), ("registrar", "innovación"), ("registrar", "invención"), ("registrar", "desarrollo tecnológico"), ("registrar", "tecnología"), ("registrar", "tecnológico"), ("registrar", "desarrollo"), ("registrar", "idea"), ("registrar", "descubrimiento"), ("registrar", "aparato"), ("registrar", "dispositivo"), ("registrar", "máquina"), ("registrar", "creación"), ("registrar", "creación tecnológica"), ("registrar", "creación científica"), ("registrar", "hallazgo"), ("registrar", "avance"), ("registrar", "avance tecnológico"), ("registrar", "avance científico"), ("registrar", "prototipo"), ("inscribir", "invento"), ("inscribir", "innovación"), ("inscribir", "invención"), ("inscribir", "desarrollo tecnológico"), ("inscribir", "tecnología"), ("inscribir", "tecnológico"), ("inscribir", "desarrollo"), ("inscribir", "idea"), ("inscribir", "descubrimiento"), ("inscribir", "aparato"), ("inscribir", "dispositivo"), ("inscribir", "máquina"), ("inscribir", "creación"), ("inscribir", "creación tecnológica"), ("inscribir", "creación científica"), ("inscribir", "hallazgo"), ("inscribir", "avance"), ("inscribir", "avance tecnológico"), ("inscribir", "avance científico"), ("inscribir", "prototipo"), ("patentar", "invento"), ("patentar", "innovación"), ("patentar", "invención"), ("patentar", "desarrollo tecnológico"), ("patentar", "tecnología"), ("patentar", "tecnológico"), ("patentar", "desarrollo"), ("patentar", "idea"), ("patentar", "descubrimiento"), ("patentar", "aparato"), ("patentar", "dispositivo"), ("patentar", "máquina"), ("patentar", "creación"), ("patentar", "creación tecnológica"), ("patentar", "creación científica"), ("patentar", "hallazgo"), ("patentar", "avance"), ("patentar", "avance tecnológico"), ("patentar", "avance científico"), ("patentar", "prototipo"), ("proteger", "invento"), ("proteger", "innovación"), ("proteger", "invención"), ("proteger", "desarrollo tecnológico"), ("proteger", "tecnología"), ("proteger", "tecnológico"), ("proteger", "desarrollo"), ("proteger", "idea"), ("proteger", "descubrimiento"), ("proteger", "aparato"), ("proteger", "dispositivo"), ("proteger", "máquina"), ("proteger", "creación"), ("proteger", "creación tecnológica"), ("proteger", "creación científica"), ("proteger", "hallazgo"), ("proteger", "avance"), ("proteger", "avance tecnológico"), ("proteger", "avance científico"), ("proteger", "prototipo"), ("legalizar", "invento"), ("legalizar", "innovación"), ("legalizar", "invención"), ("legalizar", "desarrollo tecnológico"), ("legalizar", "tecnología"), ("legalizar", "tecnológico"), ("legalizar", "desarrollo"), ("legalizar", "idea"), ("legalizar", "descubrimiento"), ("legalizar", "aparato"), ("legalizar", "dispositivo"), ("legalizar", "máquina"), ("legalizar", "creación"), ("legalizar", "creación tecnológica"), ("legalizar", "creación científica"), ("legalizar", "hallazgo"), ("legalizar", "avance"), ("legalizar", "avance tecnológico"), ("legalizar", "avance científico"), ("legalizar", "prototipo"), ("formalizar", "invento"), ("formalizar", "innovación"), ("formalizar", "invención"), ("formalizar", "desarrollo tecnológico"), ("formalizar", "tecnología"), ("formalizar", "tecnológico"), ("formalizar", "desarrollo"), ("formalizar", "idea"), ("formalizar", "descubrimiento"), ("formalizar", "aparato"), ("formalizar", "dispositivo"), ("formalizar", "máquina"), ("formalizar", "creación"), ("formalizar", "creación tecnológica"), ("formalizar", "creación científica"), ("formalizar", "hallazgo"), ("formalizar", "avance"), ("formalizar", "avance tecnológico"), ("formalizar", "avance científico"), ("formalizar", "prototipo")],
            "RDD-016": [("registrar", "robots"), ("registrar", "dróides"), ("registrar", "robot"), ("registrar", "droide"), ("inscribir", "robots"), ("inscribir", "dróides"), ("inscribir", "robot"), ("inscribir", "droide")],
            "PAT-018": [("autorizar", "aterrizaje"), ("autorizar", "desembarque"), ("autorizar", "descenso"), ("autorizar", "llegada al suelo"), ("autorizar", "llegada"), ("realizar", "aterrizaje"), ("realizar", "desembarque"), ("realizar", "descenso"), ("realizar", "llegada al suelo"), ("realizar", "llegada")],
            "CAT-019": [("verificar", "antecedentes"), ("verificar", "antecedentes penales"), ("verificar", "historial penal"), ("verificar", "conducta"), ("verificar", "comportamiento"), ("consultar", "antecedentes"), ("consultar", "antecedentes penales"), ("consultar", "historial penal"), ("consultar", "conducta"), ("consultar", "comportamiento"), ("revisar", "antecedentes"), ("revisar", "antecedentes penales"), ("revisar", "historial penal"), ("revisar", "conducta"), ("revisar", "comportamiento"), ("comprobar", "antecedentes"), ("comprobar", "antecedentes penales"), ("comprobar", "historial penal"), ("comprobar", "conducta"), ("comprobar", "comportamiento")]
            # Puedes agregar combinaciones para otros certificados según corresponda
        }
        
        # Función para calcular token_score: cuántos tokens de la consulta están en las acciones del certificado
        def token_score(cert: Dict[Text, Any], query_tokens: List[str]) -> int:
            acciones = [accion.lower() for accion in cert.get("accion", [])]
            score = 0
            for token in query_tokens:
                if token in acciones:
                    score += 1
            return score

        # Función para calcular combination_score
        def combination_score(cert_id: str, query_tokens: List[str]) -> int:
            score = 0
            for combo in priority_combinations.get(cert_id, []):
                # Verifica que ambos elementos de la combinación estén presentes en la consulta
                if all(elem in query_tokens for elem in combo):
                    score += 1
            return score

        factor_combination = 2  # Factor de ponderación para las combinaciones prioritarias

        # Calcular puntaje final para cada candidato
        candidatos_con_puntaje = []
        for cert in candidatos:
            cert_id = cert.get("ID_Documento")
            basic_score = token_score(cert, query_tokens)
            comb_score = combination_score(cert_id, query_tokens)
            final_score = basic_score + (comb_score * factor_combination)
            candidatos_con_puntaje.append((cert, final_score))

        # Ordenar candidatos por puntaje final de mayor a menor
        candidatos_con_puntaje.sort(key=lambda x: x[1], reverse=True)
        
        # Si el mejor candidato tiene puntaje mayor a 0 y es único, se selecciona; si hay empate se pide aclaración
        top_score = candidatos_con_puntaje[0][1]
        top_candidates = [cert for cert, score in candidatos_con_puntaje if score == top_score]
        
        if top_score > 0 and len(top_candidates) == 1:
            seleccionado = top_candidates[0]
        else:
            # Si hay empate o ninguno con puntaje positivo, se muestra la lista para aclaración
            nombres = "\n".join(f"- {cert.get('Nombre_Documento')}" for cert in candidatos)
            dispatcher.utter_message(
                text=f"Se encontraron varias opciones relacionadas con tu consulta:\n{nombres}\n\n¿Podrías indicar cuál te interesa?"
            )
            return []

        # Extraer datos del certificado seleccionado
        nombre_documento = seleccionado.get("Nombre_Documento")
        requisitos = seleccionado.get("Requisitos", [])
        requisitos_str = ", ".join(requisitos)
        direccion = seleccionado.get("Direccion") or seleccionado.get("Dirección", "Información no disponible")
        horario = seleccionado.get("Horario_Atencion", "Información no disponible")
        holocom = seleccionado.get("Holocom_Number", "Información no disponible")
        correo = seleccionado.get("Correo_Electronico", "Información no disponible")
        penalidad = seleccionado.get("penalidad", "Información no disponible")

        # Enviar respuestas en varios mensajes (utter)
        dispatcher.utter_message(text=f"Para tramitar el {nombre_documento} necesitas: {requisitos_str}.")
        dispatcher.utter_message(text=f"Lo puedes obtener en: {direccion}. Horario de atención: {horario}.")
        dispatcher.utter_message(text=f"Si tienes alguna duda, comunícate al número {holocom} o escribe a {correo}.")
        dispatcher.utter_message(text=f"Importante: {penalidad}")

        return []

class ActionDecirHora(Action):
    def name(self) -> Text:
        return "action_decir_hora"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        hora_actual = datetime.now().strftime("%H:%M:%S")
        logger.debug(f"ActionDecirHora ejecutada, hora actual: {hora_actual}")
        dispatcher.utter_message(text=f"La hora actual es {hora_actual}")
        return []

class ActionDecirFecha(Action):
    def name(self) -> Text:
        return "action_decir_fecha"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        logger.debug(f"ActionDecirFecha ejecutada, fecha actual: {fecha_actual}")
        dispatcher.utter_message(text=f"La fecha de hoy es {fecha_actual}.")
        return []
    

    
##### CITAS ####

# Acción 1: Mostrar horarios disponibles
class ActionScheduleMeeting(Action):
    def name(self) -> Text:
        return "action_schedule_meeting"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        try:
            with open("files/json/agend_horas.json", "r") as f:
                data = json.load(f)
        except Exception as e:
            dispatcher.utter_message(text="Error al cargar los horarios disponibles.")
            return []

        # Se recorre la lista de funcionarios y se recogen los horarios "available"
        available_slots = []
        for func in data["funcionarios"]:
            for time, slot in func["horarios"].items():
                if slot["estado"] == "available":
                    available_slots.append({
                        "funcionario": func["nom_func"],
                        "cod_fun": func["cod_fun"],
                        "hora": time
                    })
            # Si ya se encontraron horarios disponibles para un funcionario, salimos (se asigna un funcionario por solicitud)
            if available_slots:
                break

        if not available_slots:
            dispatcher.utter_message(text="Lo siento, no hay horarios disponibles para citas.")
            return []

        # Construir mensaje con las opciones disponibles
        message = "Los siguientes horarios están disponibles:\n"
        for slot in available_slots:
            message += f"{slot['hora']} con {slot['funcionario']}\n"
        dispatcher.utter_message(text=message)
        return []

# Acción 2: Confirmar la selección del horario
class ActionConfirmSchedule(Action):
    def name(self) -> Text:
        return "action_confirm_schedule"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        chosen_hour = tracker.get_slot("hora_cita")
        user_name = tracker.get_slot("nombre_completo_usuario")
        user_email = tracker.get_slot("correo_usuario")
        motivo = tracker.get_slot("motivo_cita")

        if not chosen_hour:
            dispatcher.utter_message(text="No se ha seleccionado un horario. Por favor elige un horario disponible.")
            return []

        # Cargar el archivo JSON
        try:
            with open("files/json/agend_horas.json", "r") as f:
                data = json.load(f)
        except Exception as e:
            dispatcher.utter_message(text="Error al cargar la información de citas.")
            return []

        updated = False
        # Buscar y actualizar el horario elegido
        for func in data["funcionarios"]:
            if chosen_hour in func["horarios"]:
                slot = func["horarios"][chosen_hour]
                if slot["estado"] == "available":
                    # Bloquear el slot: marcarlo como "pending"
                    slot["estado"] = "pending"
                    slot["usuario"] = user_name
                    slot["email_usuario"] = user_email
                    slot["descripcion_consulta"] = motivo
                    updated = True
                    dispatcher.utter_message(text=f"El horario {chosen_hour} con {func['nom_func']} ha sido reservado temporalmente. Por favor confirma tu cita.")
                    break

        if not updated:
            dispatcher.utter_message(text="El horario seleccionado ya no está disponible. Por favor elige otro.")
            return []

        # Guardar la actualización en el archivo JSON
        try:
            with open("files/json/agend_horas.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            dispatcher.utter_message(text="Error al guardar la reserva. Intenta nuevamente.")
            return []

        return [SlotSet("hora_cita", chosen_hour)]

# Acción 3: Enviar correo de confirmación (simulado)
class ActionSendConfirmationEmail(Action):
    def name(self) -> Text:
        return "action_send_confirmation_email"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        user_email = tracker.get_slot("correo_usuario")
        chosen_hour = tracker.get_slot("hora_cita")
        user_name = tracker.get_slot("nombre_completo_usuario")
        
        if user_email and chosen_hour and user_name:
            # Simulación del envío de correo (aquí se podría integrar con un servicio SMTP o n8n)
            confirmation_message = (f"Se ha enviado un correo de confirmación a {user_email} para tu cita a las {chosen_hour}.\n"
                                    f"¡Gracias {user_name}!")
            dispatcher.utter_message(text=confirmation_message)
        else:
            dispatcher.utter_message(text="Faltan datos para enviar la confirmación de tu cita.")
        return []

# Acción Fallback Inteligente LLM
class ActionLLMFallback(Action):
    def name(self) -> Text:
        return "action_llm_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_message = tracker.latest_message.get("text", "").strip()
        found = False
        txt_dir = "./files/txt"
        # 1. Buscar en documentos txt locales
        if os.path.isdir(txt_dir):
            for fname in os.listdir(txt_dir):
                if fname.endswith(".txt"):
                    try:
                        with open(os.path.join(txt_dir, fname), "r", encoding="utf-8") as f:
                            content = f.read()
                            if user_message.lower() in content.lower():
                                dispatcher.utter_message(text=f"Encontré esto en mis documentos: {content}")
                                found = True
                                break
                    except Exception as e:
                        continue
        # 2. Si no encontró, consulta llm-gateway
        if not found:
            try:
                llm_url = "http://llm-gateway:5000/generate"  # Ajusta la URL según tu entorno
                response = requests.post(llm_url, json={"message": user_message}, timeout=5)
                if response.status_code == 200:
                    llm_reply = response.json().get("reply", None)
                    if llm_reply:
                        dispatcher.utter_message(text=llm_reply)
                        found = True
            except Exception as e:
                pass
        # 3. Si no encontró nada, disculpa
        if not found:
            dispatcher.utter_message(text="Lo siento, no tengo una respuesta para esa pregunta en este momento.")
        return []

class ActionSendConfirmationEmail(Action):
    def name(self) -> Text:
        return "action_send_confirmation_email"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[EventType]:
        user_email = tracker.get_slot("correo_usuario")
        chosen_hour = tracker.get_slot("hora_cita")
        user_name = tracker.get_slot("nombre_completo_usuario")
        
        if user_email and chosen_hour and user_name:
            # Simulación del envío de correo (aquí se podría integrar con un servicio SMTP o n8n)
            confirmation_message = (f"Se ha enviado un correo de confirmación a {user_email} para tu cita a las {chosen_hour}.\n"
                                    f"¡Gracias {user_name}!")
            dispatcher.utter_message(text=confirmation_message)
        else:
            dispatcher.utter_message(text="Faltan datos para enviar la confirmación de tu cita.")
        return []
    
class ActionInfopersReclamo(Action):
    def name(self):
        return "action_infopers_reclamo"

    def run(self, dispatcher, tracker, domain):
        # Obtener el mensaje del usuario
        text = tracker.latest_message.get("text")
        # Se espera que el formato sea "Nombre completo, email"
        parts = text.split(',')
        if len(parts) >= 2:
            nombre = parts[0].strip()
            correo = parts[1].strip()
        else:
            # Si no se cumple el formato, se puede enviar un mensaje de error o asumir todo como nombre
            nombre = text.strip()
            correo = ""

        # Crear un diccionario con la información
        entry = {"nombre": nombre, "correo": correo}

        # Ruta del archivo JSON
        filename = "./files/json/reclamos.json"

        # Cargar datos existentes o crear lista nueva
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
        else:
            data = []

        # Agregar la nueva entrada
        data.append(entry)

        # Guardar nuevamente en el archivo JSON
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        dispatcher.utter_message(text="Gracias, he registrado tu nombre y correo.")
        # También podemos actualizar slots para uso futuro
        return [SlotSet("nombre_completo_usuario", nombre), SlotSet("correo_usuario", correo)]

class ActionProcesarAreaReclamo(Action):
    def name(self):
        return "action_procesar_area_reclamo"

    def run(self, dispatcher, tracker, domain):
        # Obtener el área ingresada por el usuario
        area = tracker.latest_message.get("text").strip().lower()

        # Ruta del archivo JSON
        filename = "./files/json/reclamos.json"

        # Cargar datos existentes
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
        else:
            data = []

        # Si hay al menos un reclamo registrado, se asocia el área al último reclamo
        if data:
            data[-1]["area"] = area
        else:
            # Si no existe, se crea una nueva entrada (esto es poco probable en un flujo correcto)
            data.append({"area": area})

        # Guardar los cambios
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        dispatcher.utter_message(text="Área registrada: " + area)
        return [SlotSet("accion_reclamo", area)]
    
class ActionRegistrarReclamo(Action):
    def name(self):
        return "action_registrar_reclamo"

    def run(self, dispatcher, tracker, domain):
        # Obtener el texto de la descripción del reclamo
        descripcion = tracker.latest_message.get("text").strip().lower()

        # Ruta del archivo JSON
        filename = "./files/json/reclamos.json"

        # Cargar datos existentes
        if os.path.exists(filename):
            with open(filename, "r") as f:
                data = json.load(f)
        else:
            data = []

        # Asumir que la última entrada corresponde al reclamo actual, y se guarda la descripción
        if data:
            data[-1]["descripcion_reclamo"] = descripcion
        else:
            data.append({"descripcion_reclamo": descripcion})

        # Guardar los cambios en el JSON
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

        dispatcher.utter_message(text="Reclamo registrado: " + descripcion)
        return []


