"""
Custom email backend for Resend email service.
Provides a Django-compatible email backend that uses Resend API.
"""

from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import resend
import logging

logger = logging.getLogger(__name__)


class ResendBackend(BaseEmailBackend):
    """
    Email backend that uses Resend API for sending emails.
    
    Resend is a modern email API optimized for developers.
    API: https://resend.com/docs
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.fail_silently = fail_silently
        
        # Initialize Resend with API key
        api_key = settings.RESEND_API_KEY
        if not api_key:
            raise ValueError("RESEND_API_KEY is not set in settings")
        
        resend.api_key = api_key
    
    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage objects and return the number of email
        messages sent.
        """
        if not email_messages:
            return 0
        
        msg_count = 0
        
        for message in email_messages:
            try:
                self._send(message)
                msg_count += 1
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.error(f"Failed to send email to {message.to}: {str(e)}")
        
        return msg_count
    
    def _send(self, message):
        """
        Send a single EmailMessage object.
        
        Args:
            message: Django EmailMessage object
        
        Raises:
            ValueError: If email sending fails and fail_silently is False
        """
        if not message.recipients():
            return False
        
        # Build email data
        email_data = {
            'from': message.from_email or settings.DEFAULT_FROM_EMAIL,
            'to': ', '.join(message.to),
            'subject': message.subject,
            'html': message.body if message.content_subtype == 'html' else None,
            'text': message.body if message.content_subtype == 'plain' else None,
        }
        
        # Use HTML if available in message alternatives
        if message.alternatives:
            for content, mime_type in message.alternatives:
                if mime_type == 'text/html':
                    email_data['html'] = content
                    # If we have HTML, use the text as fallback
                    if 'text' not in email_data or email_data['text'] is None:
                        email_data['text'] = message.body
                    break
        
        # Handle CC and BCC
        if message.cc:
            email_data['cc'] = ', '.join(message.cc)
        if message.bcc:
            email_data['bcc'] = ', '.join(message.bcc)
        
        # Handle reply-to
        if message.reply_to:
            email_data['reply_to'] = message.reply_to[0]
        
        # Send via Resend API
        try:
            response = resend.Emails.send(email_data)
            
            if response.get('id'):
                logger.info(f"✅ Email sent to {', '.join(message.to)} (ID: {response['id']})")
                return True
            else:
                error_msg = response.get('message', 'Unknown error')
                logger.error(f"❌ Failed to send email to {', '.join(message.to)}: {error_msg}")
                raise ValueError(error_msg)
        
        except Exception as e:
            logger.error(f"❌ Resend API error: {str(e)}")
            if not self.fail_silently:
                raise
            return False
