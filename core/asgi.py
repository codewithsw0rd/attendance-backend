"""
ASGI config for core project.

Exposes the ASGI callable as a module-level variable named ``application``.
Configured to handle both HTTP and WebSocket protocols via Channels.

For more information on files, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Get Django ASGI app
django_asgi_app = get_asgi_application()

# Import after Django setup
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from attendance.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # HTTP protocol - handled by Django
    "http": django_asgi_app,
    
    # WebSocket protocol - handled by Channels
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})