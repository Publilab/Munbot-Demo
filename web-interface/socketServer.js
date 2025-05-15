// web_app/socketServer.js

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const axios = require('axios');
const path = require('path');

const app = express();
const server = http.createServer(app);

// Servir archivos estáticos desde /static
app.use('/static', express.static(path.join(__dirname, 'static')));

// Servir index.html desde /templates al acceder a /
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'templates', 'index.html'));
});

// Configuración de CORS directamente en la instancia de Socket.IO
const io = new Server(server, {
    cors: {
        origin: "*", // Permite todas las orígenes. Para producción, especifica los dominios permitidos.
        methods: ["GET", "POST"]
    }
});

const RASA_URL = 'http://rasa-core:5005/webhooks/rest/webhook'; // URL anterior http://localhost:5005/webhooks/rest/webhook

io.on('connection', (socket) => {
    console.log('Un usuario se ha conectado');

    socket.on('message', async (msg) => {
    console.log('Mensaje recibido del cliente:', msg);
    const n8nWebhookUrl = process.env.N8N_WEBHOOK_URL || 'http://n8n:5678/webhook/web-interface';
    let intentos = 0;
    const maxIntentos = 7;
    const delay = ms => new Promise(res => setTimeout(res, ms));
    let exito = false;
    let response;
    while (intentos < maxIntentos && !exito) {
        try {
            response = await axios.post(n8nWebhookUrl, {
                sender: socket.id,
                message: msg
            });
            exito = true;
        } catch (error) {
            intentos++;
            if (intentos >= maxIntentos) {
                console.error('Error al comunicarse con n8n tras varios intentos:', error);
                socket.emit('bot_message', 'Lo siento, hubo un error procesando tu solicitud tras varios intentos.');
            } else {
                console.warn(`Intento ${intentos} fallido al comunicarse con n8n. Reintentando en 1s...`);
                await delay(1000);
            }
        }
    }
});

    socket.on('disconnect', () => {
        console.log('Un usuario se ha desconectado');
    });
});

// Endpoint para recibir notificaciones desde n8n y reenviarlas vía WebSocket
app.post('/api/notificacion', express.json(), (req, res) => {
    const { mensaje } = req.body;
    if (!mensaje) {
        return res.status(400).json({ error: 'Falta el campo mensaje' });
    }
    // Envía el mensaje a todos los clientes conectados
    io.emit('bot_message', mensaje);
    console.log('Mensaje enviado a todos los clientes vía WebSocket:', mensaje);
    res.json({ status: 'ok', mensaje });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Servidor WebSocket escuchando en el puerto ${PORT}`);
});
