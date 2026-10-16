from django.urls import path
from . import views

urlpatterns = [
    path("assemble_component/", views.assemble_component, name="assemble_component"),
]