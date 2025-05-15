from flask import Flask, jsonify, request, Response
from apscheduler.schedulers.background import BackgroundScheduler
import json
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests
import pytz
from datetime import datetime, timedelta
from tasks import setup_scheduler
import prometheus_client
from prometheus_client import Counter, Gauge, Histogram

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

# Métricas de Prometheus
APPOINTMENTS_CREATED = Counter('appointments_created_total', 'Total de citas creadas')
APPOINTMENTS_CONFIRMED = Counter('appointments_confirmed_total', 'Total de citas confirmadas')
EMAIL_ERRORS = Counter('email_errors_total', 'Total de errores al enviar correos')
WHATSAPP_ERRORS = Counter('whatsapp_errors_total', 'Total de errores al enviar mensajes de WhatsApp')
ACTIVE_APPOINTMENTS = Gauge('active_appointments', 'Número de citas activas')
REMINDER_DURATION = Histogram('reminder_duration_seconds', 'Duración del proceso de envío de recordatorios')

# Configuración de WhatsApp (Meta Cloud API)
META_PHONE_ID = os.getenv('META_PHONE_ID')
META_TOKEN = os.getenv('META_TOKEN')

# Función para enviar recordatorio
def send_reminder():
    with prometheus_client.REGISTRY.timer() as timer:
        with open('data/appointments.json', 'r') as f:
            citas = json.load(f)['citas']
        
        tomorrow = datetime.now(pytz.timezone('America/Santiago')) + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        
        for cita in citas:
            if cita['fecha'] == tomorrow_str and cita['AVLB'] == 0 and cita['USU_CONF'] == 1:
                # Enviar correo
                send_email(cita)
                # Enviar WhatsApp (si hay número)
                if cita['USU_WHATSAPP']:
                    send_whatsapp(cita)
        
        # Actualizar métrica de duración
        REMINDER_DURATION.observe(timer.sum())

# Función de correo (SendGrid)
def send_email(cita):
    message = Mail(
        from_email=os.getenv('SENDER_EMAIL'),
        to_emails=cita['USU_MAIL'],
        subject='Recordatorio de cita',
        plain_text_content=f"Su cita es mañana {cita['fecha']} a las {cita['hora']} con {cita['FUNC']}."
    )
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        EMAIL_ERRORS.inc()
        app.logger.error(f"Error en correo: {str(e)}")

# Función de WhatsApp (Meta Cloud API)
def send_whatsapp(cita):
    try:
        import requests
        phone_number = cita['USU_WHATSAPP'].replace('+', '')
        url = f"https://graph.facebook.com/v19.0/{META_PHONE_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": { "body": f"Recordatorio: Su cita es mañana {cita['fecha']} a las {cita['hora']} con {cita['FUNC']}." }
        }
        headers = {
            "Authorization": f"Bearer {META_TOKEN}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
    except Exception as e:
        WHATSAPP_ERRORS.inc()
        app.logger.error(f"Error en WhatsApp: {str(e)}")

# Programar el recordatorio diario
scheduler.add_job(
    send_reminder,
    'cron',
    hour=9,  # A las 9 AM en Santiago
    minute=0,
    id='daily_reminder'
)

# Endpoint para crear cita (agregado validación de confirmación)
@app.route('/create-appointment', methods=['POST'])
def create_appointment():
    data = request.json
    required_fields = ["MOTIV", "USU_NAME", "USU_MAIL", "USU_WHATSAPP"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"Falta {field}"}), 400

    with open('data/appointments.json', 'r') as f:
        citas = json.load(f)['citas']
    
    selected = next(
        (c for c in citas 
         if c["AVLB"] == 1 
         and c["fecha"] == data["fecha"]
         and c["hora"] == data["hora"]),
        None
    )

    if not selected:
        return jsonify({"error": "No hay citas disponibles"}), 404

    selected['MOTIV'] = data['MOTIV']
    selected['USU_NAME'] = data['USU_NAME']
    selected['USU_MAIL'] = data['USU_MAIL']
    selected['USU_WHATSAPP'] = data['USU_WHATSAPP']
    selected['AVLB'] = 0  # Marcamos como ocupado

    with open('data/appointments.json', 'w') as f:
        json.dump({"citas": citas}, f, indent=4)
    
    # Incrementar contador de citas creadas
    APPOINTMENTS_CREATED.inc()
    
    # Actualizar número de citas activas
    active_count = sum(1 for c in citas if c['AVLB'] == 0)
    ACTIVE_APPOINTMENTS.set(active_count)

    return jsonify(selected), 201

# Endpoint para confirmar cita (actualizar USU_CONF)
@app.route('/confirm-appointment/<string:id>', methods=['POST'])
def confirm_appointment(id):
    with open('data/appointments.json', 'r') as f:
        citas = json.load(f)['citas']
    
    for cita in citas:
        if cita['ID'] == id and cita['AVLB'] == 0:
            cita['USU_CONF'] = 1
            with open('data/appointments.json', 'w') as f:
                json.dump({"citas": citas}, f, indent=4)
            
            # Incrementar contador de citas confirmadas
            APPOINTMENTS_CONFIRMED.inc()
            
            return jsonify({"status": "confirmada"}), 200

    return jsonify({"error": "Cita no encontrada"}), 404

# Endpoint para métricas de Prometheus
@app.route('/metrics', methods=['GET'])
def metrics():
    if os.getenv('ENABLE_METRICS', 'false').lower() == 'true':
        return Response(prometheus_client.generate_latest(), mimetype='text/plain')
    else:
        return jsonify({"error": "Métricas no habilitadas"}), 404

if __name__ == "__main__":
    setup_scheduler()  # Iniciar el scheduler al iniciar el servicio
    # Inicializar métricas con valores iniciales
    try:
        with open('data/appointments.json', 'r') as f:
            citas = json.load(f)['citas']
            active_count = sum(1 for c in citas if c['AVLB'] == 0)
            ACTIVE_APPOINTMENTS.set(active_count)
    except Exception as e:
        app.logger.error(f"Error al inicializar métricas: {str(e)}")
    
    app.run(host='0.0.0.0', port=6001)