from flask import Flask, request, jsonify
from flask_mail import Mail, Message
import os
import json
import uuid
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

load_dotenv('config.env')

app = Flask(__name__)

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)

# Ruta del archivo JSON
DATA_FILE = 'data/reclamos.json'

# Modelo de Pydantic para validación
class ComplaintModel(BaseModel):
    nombre_denunciante: str
    mail: str
    mensaje: str
    categoria: int  # 1=reclamo, 2=denuncia
    departamento: int  # 1=seguridad, 2=obras, 3=ambiente, 4=otros

@app.route('/complaint', methods=['POST'])
def complaint():
    try:
        # Validar datos con Pydantic
        data = ComplaintModel(**request.json)
        complaint_id = str(uuid.uuid4())
        
        # Leer datos existentes (si hay)
        try:
            with open(DATA_FILE, 'r') as f:
                existing_data = json.load(f)
        except FileNotFoundError:
            existing_data = []

        # Agregar nuevo reclamo
        new_entry = {
            "id": complaint_id,
            "categoria": data.categoria,
            "departamento": data.departamento,
            "mensaje": data.mensaje,
            "nombre_denunciante": data.nombre_denunciante,
            "mail": data.mail,
            "ip": request.remote_addr  # Capturar IP del usuario
        }
        existing_data.append(new_entry)

        # Guardar en JSON
        with open(DATA_FILE, 'w') as f:
            json.dump(existing_data, f, indent=4)
        
        # Enviar correo
        send_email(new_entry)
        
        return jsonify({"message": "Reclamo registrado", "id": complaint_id}), 200

    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Error interno", "detail": str(e)}), 500

def send_email(complaint):
    try:
        msg = Message(
            f"Reclamo #{complaint['id']} recibido",
            sender="no-reply@dominio.com",
            recipients=[complaint['mail']]
        )
        msg.body = f"""
        Su reclamo ha sido asignado al departamento {complaint['departamento']}.
        ID de seguimiento: {complaint['id']}
        """
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Error al enviar email: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)