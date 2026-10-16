from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import AssemblyLogSerializer


@api_view(["POST"])
def assemble_component(request):
    serializer = AssemblyLogSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            {"status": "Failure", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    log = serializer.save()
    return Response(
        {"status": "Success", "message": "Component assembled", "log_id": log.id},
        status=status.HTTP_201_CREATED,
    )