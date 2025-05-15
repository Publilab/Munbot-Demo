require('dotenv').config();
const express = require('express');
const { v4: uuidv4 } = require('uuid');
const Complaint = require('./models/Complaint');
const sendEmail = require('./utils/email');
const app = express();
app.use(express.json());

// Conexión a MongoDB (configurada en config/db.js)
const mongoose = require('mongoose');
mongoose.connect(process.env.MONGODB_URI, { useNewUrlParser: true, useUnifiedTopology: true });

// Clasificación de reclamos (ejemplo con keywords)
function classifyComplaint(description) {
  const keywords = {
    seguridad: ['seguridad', 'delito', 'robo'],
    obras: ['bache', 'iluminación', 'acoso'],
    ambiente: ['basura', 'contaminación', 'ruido']
  };
  const lowerDescription = description.toLowerCase();
  for (const department in keywords) {
    if (keywords[department].some(word => lowerDescription.includes(word))) {
      return department;
    }
  }
  return 'otro'; // Departamento predeterminado
}

// Endpoint de salud para monitoreo
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', message: 'Complaints API saludable' });
});

// Endpoint para crear reclamos
app.post('/complaint', async (req, res) => {
  try {
    const { name, email, description } = req.body;
    if (!name || !email || !description) {
      return res.status(400).json({ error: 'Faltan campos requeridos' });
    }

    // Generar ID único
    const complaintId = uuidv4();

    // Clasificar reclamo
    const department = classifyComplaint(description);

    // Guardar en MongoDB
    const complaint = new Complaint({
      complaintId,
      name,
      email,
      description,
      department,
      status: 'pendiente'
    });
    await complaint.save();

    // Enviar email al usuario
    await sendEmail(email, `Reclamo ${complaintId} recibido`, `Su reclamo ha sido asignado al departamento ${department}. ID: ${complaintId}`);

    res.json({ message: 'Reclamo registrado', complaintId });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error interno del servidor' });
  }
});

// Configuración de puerto
const PORT = process.env.PORT || 7000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});