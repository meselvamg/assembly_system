from django.urls import path
from . import views

urlpatterns = [
    path("assemble_component/", views.assemble_component, name="assemble_component"),
    path("verify_component/", views.verify_component, name="verify_component"),
    path("scada_integration/", views.scada_integration, name="scada_integration"),
    path("report_to_cloud/", views.report_to_cloud, name="report_to_cloud"),
    path("authorize_user/", views.authorize_user, name="authorize_user"),
    path("dashboard_data/", views.dashboard_data, name="dashboard_data"),
]
