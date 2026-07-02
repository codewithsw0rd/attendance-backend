from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from .routers import router
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from accounts.api.api_view import GetProfileView
from core.utils.custom_tokens import CustomTokenObtainPairView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),  # Root level, no /api/
    path('profile/', GetProfileView.as_view(), name='get_profile'),
]

# auth urls
urlpatterns += [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

# API documentation urls
urlpatterns += [
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redocs/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]