import adrf.decorators as async_support
from django.urls import re_path, path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import authentication_classes
from rest_framework.settings import api_settings
from strawberry.django.views import AsyncGraphQLView
from proxy.views import proxy_view

from openbook.graphql_schema import schema
from openbook.webhooks import NotificationWebhook, OryWebhook


class AuthenticatedStrawberryGraphQLView(AsyncGraphQLView):
    @classmethod
    def as_view(cls, *args, **kwargs):
        view = super(AuthenticatedStrawberryGraphQLView, cls).as_view(*args, **kwargs)
        view = authentication_classes(api_settings.DEFAULT_AUTHENTICATION_CLASSES)(view)
        view = async_support.api_view(["GET", "POST"])(view)
        return view


urlpatterns = [
    path(f"{settings.ENVIRONMENT_ID}/admin/", admin.site.urls),
    path("admin/", admin.site.urls, name="admin-endpoint"),
    path("django-rq/", include("django_rq.urls")),
    path("graphql", csrf_exempt(AuthenticatedStrawberryGraphQLView.as_view(schema=schema)), name="graphql-endpoint"),
    path("notification-webhook", csrf_exempt(NotificationWebhook.as_view()), name="notification-webhook-endpoint"),
    path("ory-webhook", csrf_exempt(OryWebhook.as_view()), name="ory-webhook-endpoint"),
]

# The static helper works only in debug mode
# https://docs.djangoproject.com/en/2.1/howto/static-files/#serving-files-uploaded-by-a-user-during-development
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]
# Link previews proxy their urls, use local proxy API on debug/test
if settings.DEBUG or settings.TESTING:
    urlpatterns.append(
        re_path("proxy/(?P<url>.*)", proxy_view, name="proxy"),
    )
