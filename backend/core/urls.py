"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from planning.views import plan_trip, render_logbook
from django.urls import path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # --- Main API endpoints ---
    # Underscore, no slash (original)
    path("api/plan_trip", plan_trip, name="plan_trip"),
    path("api/logbook", render_logbook, name="logbook"),

    # Friendly aliases: hyphen + trailing slashes
    path("api/plan-trip/", plan_trip, name="plan_trip_dash"),
    path("api/logbook/", render_logbook, name="logbook_slash"),

    # --- OpenAPI / Swagger ---
    path("api/schema/", SpectacularAPIView.as_view(api_version="1.0.0"), name="schema"),
    path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
