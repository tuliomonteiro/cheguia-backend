from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import JsonResponse
import json


@api_view(['POST'])
@permission_classes([AllowAny])
def chat(request):
    """
    Basic chat endpoint for AI interaction
    This will be enhanced with OpenAI integration in the next step
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        
        if not user_message:
            return Response(
                {'error': 'Message is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # For now, return a simple response
        # This will be replaced with OpenAI integration
        ai_response = {
            'message': f"Hola! Recibí tu mensaje: '{user_message}'. Soy tu asistente de Paraguay. Pronto podré ayudarte con información sobre trámites y documentos.",
            'sources': [],
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        return Response(ai_response, status=status.HTTP_200_OK)
        
    except json.JSONDecodeError:
        return Response(
            {'error': 'Invalid JSON'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'message': 'Paraguay Guide API is running',
        'version': '1.0.0'
    })