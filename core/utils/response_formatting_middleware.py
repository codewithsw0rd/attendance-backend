from django.utils.deprecation import MiddlewareMixin
from rest_framework.response import Response


class ResponseFormatterMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path.startswith('/api/docs/') or request.path.startswith('/api/schema/'):
            return response
        if isinstance(response, Response):
            if not isinstance(response.data, dict) or "success" not in response.data:
                if 200 <= response.status_code < 400:
                    response.data = {
                        "success": True,
                        "data": response.data if response.data is not None else {},
                    }
                else:
                    error_content = {}
                    if isinstance(response.data, dict) and "error" in response.data:
                        error_content = response.data["error"]
                    elif response.data is not None:
                        error_content = response.data
                    response.data = {
                        "success": False,
                        "error": error_content,
                    }

                response._is_rendered = False
                response.render()

        return response