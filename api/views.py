from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000)
    session_id = serializers.UUIDField(required=False)


@api_view(['POST'])
def chat(request):
    """
    Stateless quick-chat endpoint. Will be wired to OpenAI in step 3.
    Uses the default permission from settings (IsAuthenticated in prod, AllowAny in dev).
    """
    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user_message = serializer.validated_data['message']

    return Response({
        'message': (
            f"Hola! Recibí tu mensaje: '{user_message}'. "
            "Soy tu asistente de Paraguay. Pronto podré ayudarte con "
            "información sobre trámites y documentos."
        ),
        'sources': [],
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({
        'status': 'healthy',
        'message': 'Paraguay Guide API is running',
        'version': '1.0.0',
    })
