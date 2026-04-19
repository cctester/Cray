"""
Email plugin - send emails via SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger

from cray.plugins import Plugin


class EmailPlugin(Plugin):
    """Plugin for sending emails."""
    
    name = "email"
    description = "Send emails via SMTP"
    
    @property
    def actions(self):
        return {
            "send": {"description": "Send email", "params": [{"name": "smtp_host", "type": "string", "required": True, "description": "SMTP server"}, {"name": "smtp_port", "type": "number", "required": False, "description": "SMTP port"}, {"name": "from", "type": "string", "required": True, "description": "From address"}, {"name": "to", "type": "string", "required": True, "description": "To address"}, {"name": "subject", "type": "string", "required": True, "description": "Subject"}, {"name": "body", "type": "string", "required": True, "description": "Email body"}]},
            "send_template": {"description": "Send email with template", "params": [{"name": "smtp_host", "type": "string", "required": True, "description": "SMTP server"}, {"name": "template", "type": "string", "required": True, "description": "Template name"}]},
        }
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an email action."""
        
        actions = {
            "send": self._send,
            "send_template": self._send_template,
        }
        
        if action not in actions:
            raise ValueError(f"Unknown action: {action}")
        
        return await actions[action](params)
    
    async def _send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email."""
        
        # Required parameters
        to = params.get("to")
        subject = params.get("subject", "")
        body = params.get("body", "")
        
        if not to:
            raise ValueError("Missing required parameter: to")
        
        # SMTP configuration (can be set in params or defaults)
        smtp_host = params.get("smtp_host", "localhost")
        smtp_port = params.get("smtp_port", 25)
        smtp_user = params.get("smtp_user")
        smtp_password = params.get("smtp_password")
        use_tls = params.get("use_tls", False)
        
        # From address
        from_addr = params.get("from", smtp_user or "cray@localhost")
        
        # Handle multiple recipients
        if isinstance(to, str):
            to = [to]
        
        # Create message
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        
        # Body
        content_type = params.get("content_type", "plain")
        msg.attach(MIMEText(body, content_type))
        
        # Attachments
        attachments = params.get("attachments", [])
        for attachment in attachments:
            self._attach_file(msg, attachment)
        
        logger.debug(f"Sending email to: {to}")
        
        try:
            # Connect and send
            if use_tls:
                smtp = smtplib.SMTP(smtp_host, smtp_port)
                smtp.starttls()
            else:
                smtp = smtplib.SMTP(smtp_host, smtp_port)
            
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            
            smtp.sendmail(from_addr, to, msg.as_string())
            smtp.quit()
            
            return {
                "to": to,
                "subject": subject,
                "success": True,
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {
                "to": to,
                "subject": subject,
                "success": False,
                "error": str(e),
            }
    
    async def _send_template(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email using a template."""
        
        template = params.get("template", "")
        variables = params.get("variables", {})
        
        # Substitute variables in template
        body = template
        for key, value in variables.items():
            body = body.replace(f"{{{{{key}}}}}", str(value))
        
        # Send with substituted body
        send_params = {**params, "body": body}
        return await self._send(send_params)
    
    def _attach_file(self, msg: MIMEMultipart, attachment: Any) -> None:
        """Attach a file to the message."""
        
        if isinstance(attachment, str):
            path = Path(attachment)
            if not path.exists():
                logger.warning(f"Attachment not found: {path}")
                return
            
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={path.name}"
                )
                msg.attach(part)
        
        elif isinstance(attachment, dict):
            # Inline attachment with content
            filename = attachment.get("filename", "attachment")
            content = attachment.get("content", "")
            content_type = attachment.get("content_type", "text/plain")
            
            part = MIMEText(content, _subtype=content_type.split("/")[-1])
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}"
            )
            msg.attach(part)
