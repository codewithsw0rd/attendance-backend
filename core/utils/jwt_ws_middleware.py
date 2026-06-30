from urllib.parse import parse_qs

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from accounts.models import CustomUser


@database_sync_to_async
def get_user_from_token(token: str):
    try:
        validated = AccessToken(token)
        user_id = validated.get("user_id")
        if not user_id:
            return AnonymousUser()
        return CustomUser.objects.get(id=user_id)
    except (CustomUser.DoesNotExist, InvalidToken, TokenError, Exception):
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        if token:
            scope["user"] = await get_user_from_token(token)

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return AuthMiddlewareStack(JWTAuthMiddleware(inner))
