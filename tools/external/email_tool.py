"""
Tool: email
Envía correos electrónicos usando Gmail SMTP.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from core.interfaces import Tool, ToolResult

load_dotenv()


class EmailTool(Tool):
    name = "email"
    description = (
        "Envía un correo electrónico. Usa esto cuando el usuario pida enviar "
        "un email, correo o mensaje a alguien."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Dirección de correo del destinatario"
            },
            "subject": {
                "type": "string",
                "description": "Asunto del correo"
            },
            "body": {
                "type": "string",
                "description": "Contenido del correo"
            }
        },
        "required": ["to", "subject", "body"]
    }

    def execute(self, params: dict) -> ToolResult:
        to      = params.get("to", "").strip()
        subject = params.get("subject", "").strip()
        body    = params.get("body", "").strip()

        if not to or not subject or not body:
            return ToolResult.fail("Faltan datos: necesito destinatario, asunto y mensaje.")

        gmail_user     = os.getenv("GMAIL_USER", "")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD", "")

        if not gmail_user or not gmail_password:
            return ToolResult.fail("No se encontraron las credenciales de Gmail en el .env.")

        try:
            msg = MIMEMultipart()
            msg["From"]    = gmail_user
            msg["To"]      = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_user, gmail_password)
                server.sendmail(gmail_user, to, msg.as_string())

            return ToolResult.ok(f"Correo enviado correctamente a {to}.")

        except smtplib.SMTPAuthenticationError:
            return ToolResult.fail("Error de autenticación. Verifica tu correo y contraseña de aplicación.")
        except smtplib.SMTPException as e:
            return ToolResult.fail(f"Error al enviar el correo: {e}")
        except Exception as e:
            return ToolResult.fail(f"Error inesperado: {e}")
