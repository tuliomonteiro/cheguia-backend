from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from ai.service import get_response, AIServiceError


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000)


@api_view(['POST'])
def chat(request):
    """
    Stateless quick-chat endpoint (no session history).
    Uses default permission: IsAuthenticated in prod, AllowAny in dev.
    """
    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        result = get_response(serializer.validated_data['message'])
    except AIServiceError as exc:
        return Response({'error': str(exc)}, status=exc.status_code)

    return Response({
        'message': result['message'],
        'sources': result['sources'],
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({
        'status': 'healthy',
        'message': 'Paraguay Guide API is running',
        'version': '1.0.0',
    })
