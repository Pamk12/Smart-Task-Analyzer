from django.urls import path
from .views import analyze_tasks, suggest_tasks

urlpatterns = [
    path("analyze/", analyze_tasks, name="analyze_tasks"),
    path("suggest/", suggest_tasks, name="suggest_tasks"),
]
