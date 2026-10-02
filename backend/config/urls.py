"""type-10022026-Maurice: Authentication and role-shell routes."""
from django.urls import include, path

urlpatterns = [path("api/", include("backend.users.urls"))]
