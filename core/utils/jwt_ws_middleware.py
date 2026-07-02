from urllib.parse import parse_qs
import logging

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from accounts.models import CustomUser

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token: str):
    try:
        if not token or not isinstance(token, str):
            logger.warning(f"Invalid token format: {type(token)}")
            return AnonymousUser()
        
        logger.info(f"Attempting to validate token: {token[:20]}...")
        validated = AccessToken(token)
        user_id = validated.get("user_id")
        if not user_id:
            logger.warning("Token validated but no user_id found")
            return AnonymousUser()
        
        user = CustomUser.objects.get(id=user_id)
        logger.info(f"User authenticated: {user_id}")
        return user
    except CustomUser.DoesNotExist:
        logger.warning(f"User not found for id from token")
        return AnonymousUser()
    except InvalidToken as e:
        logger.warning(f"Invalid token: {str(e)}")
        return AnonymousUser()
    except TokenError as e:
        logger.warning(f"Token error: {str(e)}")
        return AnonymousUser()
    except Exception as e:
        logger.error(f"Error in get_user_from_token: {str(e)}", exc_info=True)
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        logger.debug(f"Query string: {query_string}")
        
        params = parse_qs(query_string)
        logger.debug(f"Parsed params keys: {list(params.keys())}")
        
        token = params.get("token", [None])[0]
        
        if token:
            logger.info(f"Token found in query params: {token[:20]}...")
            scope["user"] = await get_user_from_token(token)
        else:
            logger.warning("No token found in query parameters")
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return AuthMiddlewareStack(JWTAuthMiddleware(inner))
