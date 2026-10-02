"""type-10022026-Maurice: FHIR R4 read/search routes."""
from django.urls import path
from .fhir import FHIRFacadeView

urlpatterns = [
    path("", FHIRFacadeView.as_view()),
    path("<str:resource_id>/", FHIRFacadeView.as_view()),
]
