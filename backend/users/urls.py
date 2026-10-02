"""type-10022026-Maurice: Authentication API routes."""
from django.urls import path
from . import views
from .smart import DeveloperAppsView, DeveloperAppRevokeView, AuthorizationView, TokenView, RevokeTokenView, LaunchView, smart_configuration

urlpatterns = [
    path("auth/login/", views.login_view), path("auth/enroll/", views.enroll_view),
    path("auth/enroll/verify/", views.verify_enrollment_view), path("auth/session/", views.session_view),
    path("auth/logout/", views.logout_view), path("shell/", views.shell_view),
    path("patients/", views.PatientCollectionView.as_view()),
    path("patients/<str:public_id>/", views.PatientDetailView.as_view()),
    path("patients/<str:public_id>/exports/", views.PatientExportView.as_view()),
    path("patients/<str:public_id>/exports/<uuid:artifact_id>/", views.PatientExportView.as_view()),
    path("exports/<uuid:artifact_id>/download/", views.PatientExportDownloadView.as_view()),
    path("patients/<str:public_id>/devices/", views.DeviceCollectionView.as_view()),
    path("patients/<str:public_id>/medications/", views.MedicationCollectionView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/", views.MedicationDetailView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/history/", views.MedicationHistoryView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/cancel/", views.MedicationCancelView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/refill/", views.MedicationRefillView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/evaluate/", views.MedicationEvaluateView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/acknowledge/", views.MedicationAcknowledgeView.as_view()),
    path("patients/<str:public_id>/medications/<int:order_id>/sign/", views.MedicationSignView.as_view()),
    path("admin/interaction-rules/", views.InteractionRuleAdminView.as_view()),
    path("admin/interaction-rules/<int:rule_id>/", views.InteractionRuleDetailAdminView.as_view()),
    path("admin/users/", views.AdminUserView.as_view()),
    path("admin/users/<int:user_id>/", views.AdminUserDetailView.as_view()),
    path("audit/", views.AuditReportView.as_view()),
    path("audit/verify/", views.AuditVerifyView.as_view()),
    path("smart/apps/", DeveloperAppsView.as_view()),
    path("smart/apps/<str:client_id>/", DeveloperAppRevokeView.as_view()),
    path("smart-configuration/", smart_configuration),
    path("oauth/authorize/", AuthorizationView.as_view()),
    path("oauth/token/", TokenView.as_view()),
    path("oauth/revoke_token/", RevokeTokenView.as_view()),
    path("smart/launch/", LaunchView.as_view()),
]
