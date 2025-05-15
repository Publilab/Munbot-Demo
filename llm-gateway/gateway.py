from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from sklearn.metrics.pairwise import cosine_similarity
import traceback
import logging
from logging.handlers import RotatingFileHandler
from typing import List
import glob
from llama_cpp import Llama

nltk.download('punkt')

app = FastAPI()

# Configuración CORS (ajustar orígenes según necesidad)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seguridad básica HTTP (puede ser reemplazada por JWT o IP whitelist)
security = HTTPBasic()
ALLOWED_IPS = os.getenv("ALLOWED_IPS", "127.0.0.1").split(",")
API_USERNAME = os.getenv("API_USERNAME", "admin")
API_PASSWORD = os.getenv("API_PASSWORD", "admin")

# Logging estructurado y rotación de logs
log_path = os.getenv("LOG_PATH", "gateway.log")
log_handler = RotatingFileHandler(log_path, maxBytes=2*1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[log_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class QuestionRequest(BaseModel):
    question: str

# Middleware para restringir IPs
class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        if client_ip not in ALLOWED_IPS:
            logger.warning(f"Bloqueo de IP no permitida: {client_ip}")
            return JSONResponse(status_code=403, content={"detail": "IP no autorizada"})
        return await call_next(request)

app.add_middleware(IPWhitelistMiddleware)

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = API_USERNAME
    correct_password = API_PASSWORD
    if credentials.username != correct_username or credentials.password != correct_password:
        logger.warning(f"Intento de autenticación fallido para usuario: {credentials.username}")
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return credentials

# --- Documentación de endpoints ---
@app.get("/endpoints", tags=["documentación"])
def list_endpoints():
    return {
        "endpoints": [
            {"path": "/process", "method": "POST", "desc": "Procesa una pregunta y responde usando contexto municipal."},
            {"path": "/rasa-action", "method": "POST", "desc": "Recibe acciones personalizadas desde Rasa y responde según lógica definida."},
            {"path": "/endpoints", "method": "GET", "desc": "Lista los endpoints disponibles."},
            {"path": "/health", "method": "GET", "desc": "Verifica el estado básico del servicio."},
            {"path": "/metrics", "method": "GET", "desc": "Expone métricas Prometheus para monitoreo."}
        ]
    }

# --- Endpoint de métricas Prometheus ---
@app.get("/metrics")
def metrics():
    try:
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error al generar métricas Prometheus: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Error al generar métricas Prometheus")

# --- Configuración del modelo Llama-3-8B-Q4_K_M ---
LLAMA_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'llm-models', 'meta-llama-3-8b-instruct.Q4_K_M.gguf')
llama_model = None

def load_llama_model():
    global llama_model
    if llama_model is None:
        llama_model = Llama(model_path=LLAMA_MODEL_PATH, n_ctx=2048, n_threads=4)
    return llama_model

# --- Utilidad para buscar en documentos txt ---
def buscar_en_documentos(pregunta, documentos_dir=None):
    if documentos_dir is None:
        documentos_dir = os.path.join(os.path.dirname(__file__), 'documents', 'clean')
    archivos = glob.glob(os.path.join(documentos_dir, '*.txt'))
    corpus = []
    nombres = []
    for archivo in archivos:
        with open(archivo, 'r', encoding='utf-8') as f:
            corpus.append(f.read())
            nombres.append(os.path.basename(archivo))
    if not corpus:
        return None, None
    vectorizer = TfidfVectorizer().fit(corpus + [pregunta])
    pregunta_vec = vectorizer.transform([pregunta])
    corpus_vec = vectorizer.transform(corpus)
    similitudes = cosine_similarity(pregunta_vec, corpus_vec)[0]
    idx_max = similitudes.argmax()
    if similitudes[idx_max] > 0.2:  # Umbral configurable
        return corpus[idx_max], nombres[idx_max]
    return None, None

# --- Endpoint principal para preguntas ---
@app.post("/process", tags=["consulta"])
def process_question(req: QuestionRequest, credentials: HTTPBasicCredentials = Depends(authenticate)):
    pregunta = req.question.strip()
    # 1. Buscar primero en documentos
    contexto, doc_name = buscar_en_documentos(pregunta)
    if contexto:
        logger.info(f"Respuesta encontrada en documento: {doc_name}")
        return {"respuesta": contexto, "fuente": doc_name, "tipo": "documento"}
    # 2. Si no hay respuesta relevante, consultar el modelo Llama
    try:
        model = load_llama_model()
        prompt = f"Pregunta: {pregunta}\nResponde de forma clara y concisa."
        output = model(prompt, max_tokens=256, stop=["\n"])
        respuesta = output["choices"][0]["text"].strip()
        logger.info("Respuesta generada por Llama-3-8B-Q4_K_M")
        return {"respuesta": respuesta, "fuente": "llama-3-8b", "tipo": "modelo"}
    except Exception as e:
        logger.error(f"Error al consultar el modelo Llama: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al consultar el modelo Llama")

# --- Endpoint para fallback de Rasa ---
@app.post("/rasa-action", tags=["rasa"])
def rasa_fallback(req: QuestionRequest, credentials: HTTPBasicCredentials = Depends(authenticate)):
    pregunta = req.question.strip()
    # Evitar recurrencia: solo permitir un fallback por pregunta
    if hasattr(req, 'fallback_done') and req.fallback_done:
        logger.warning("Recurrencia de fallback detectada. Respondiendo con mensaje de control.")
        return {"respuesta": "No se pudo encontrar una respuesta adecuada. Por favor, reformula tu pregunta.", "tipo": "control"}
    # Buscar primero en documentos
    contexto, doc_name = buscar_en_documentos(pregunta)
    if contexto:
        logger.info(f"Fallback: respuesta encontrada en documento: {doc_name}")
        return {"respuesta": contexto, "fuente": doc_name, "tipo": "documento"}
    # Consultar modelo Llama
    try:
        model = load_llama_model()
        prompt = f"Pregunta: {pregunta}\nResponde de forma clara y concisa."
        output = model(prompt, max_tokens=256, stop=["\n"])
        respuesta = output["choices"][0]["text"].strip()
        logger.info("Fallback: respuesta generada por Llama-3-8B-Q4_K_M")
        return {"respuesta": respuesta, "fuente": "llama-3-8b", "tipo": "modelo"}
    except Exception as e:
        logger.error(f"Error en fallback de Rasa: {str(e)}")
        raise HTTPException(status_code=500, detail="Error en fallback de Rasa")
