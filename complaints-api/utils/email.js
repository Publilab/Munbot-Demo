const nodemailer = require('nodemailer');

async function sendEmail(to, subject, text) {
  const transporter = nodemailer.createTransport({
    host: process.env.EMAIL_HOST,
    port: process.env.EMAIL_PORT,
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_PASS
    }
  });

  const info = await transporter.sendMail({
    from: '"Servicio de Reclamos" <no-reply@dominio.com>',
    to,
    subject,
    text
  });
  console.log('Email enviado:', info.messageId);
}

module.exports = sendEmail;