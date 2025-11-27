from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .scoring import normalize_tasks, score_tasks, DEFAULT_STRATEGY

# Simple in-memory store for "suggest today" (good enough for this assignment demo)
LAST_SCORED = None


@api_view(["POST"])
def analyze_tasks(request):
    global LAST_SCORED

    if not isinstance(request.data, list):
        return Response({"error": "Expected a JSON array (list) of tasks."}, status=status.HTTP_400_BAD_REQUEST)

    strategy = request.query_params.get("strategy", DEFAULT_STRATEGY)

    tasks, warnings = normalize_tasks(request.data)
    result = score_tasks(tasks, strategy=strategy)
    result["warnings"] = warnings

    LAST_SCORED = result["tasks"]
    return Response(result)


@api_view(["GET"])
def suggest_tasks(request):
    if not LAST_SCORED:
        return Response(
            {"error": "No tasks analyzed yet. Call POST /api/tasks/analyze/ first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    top3 = LAST_SCORED[:3]
    return Response({"tasks": top3})
