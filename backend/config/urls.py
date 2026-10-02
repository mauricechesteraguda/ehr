"""type-10022026-Maurice: Authentication and role-shell routes."""
from django.urls import include, path
from backend.users.fhir import FHIRFacadeView
from backend.users.smart import smart_configuration, capability_statement, AuthorizationView, TokenView, RevokeTokenView
from backend.users.health import live, ready, beat

urlpatterns = [path("api/", include("backend.users.urls")), path("api/health/live/", live), path("api/health/ready/", ready), path("api/health/beat/", beat)]
urlpatterns.append(path("fhir/R4/<str:resource_name>/", include("backend.users.fhir_urls")))
urlpatterns.extend([
    path(".well-known/smart-configuration", smart_configuration),
    # type-10022026-Maurice: Keep discovery-advertised OAuth endpoints available
    # at their standards-facing root paths as well as the authenticated API namespace.
    path("oauth/authorize/", AuthorizationView.as_view()),
    path("oauth/token/", TokenView.as_view()),
    path("oauth/revoke_token/", RevokeTokenView.as_view()),
    path("fhir/metadata", capability_statement),
    path("fhir/R4/<str:resource_name>", FHIRFacadeView.as_view()),
    path("fhir/R4/<str:resource_name>/<str:resource_id>", FHIRFacadeView.as_view()),
])
