"""type-10022026-Maurice: Authentication API routes."""
from django.urls import path
from . import views

urlpatterns = [
    path("auth/login/", views.login_view), path("auth/enroll/", views.enroll_view),
    path("auth/enroll/verify/", views.verify_enrollment_view), path("auth/session/", views.session_view),
    path("auth/logout/", views.logout_view), path("shell/", views.shell_view),
    path("patients/", views.PatientCollectionView.as_view()),
    path("patients/<str:public_id>/", views.PatientDetailView.as_view()),
    path("patients/<str:public_id>/devices/", views.DeviceCollectionView.as_view()),
    path("patients/<str:public_id>/medications/", views.MedicationCollectionView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/", views.MedicationDetailView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/history/", views.MedicationHistoryView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/cancel/", views.MedicationCancelView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/refill/", views.MedicationRefillView.as_view()),
    path("audit/", views.AuditReportView.as_view()),
    path("audit/verify/", views.AuditVerifyView.as_view()),
]
