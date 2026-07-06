from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from ai.exceptions import AIServiceError
from ai.service import get_response
from .models import ChatSession, Message
from .serializers import ChatSessionSerializer, ChatSessionDetailSerializer, MessageSerializer


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def session_list_create(request):
    if request.method == 'GET':
        sessions = ChatSession.objects.filter(user=request.user)
        return Response(ChatSessionSerializer(sessions, many=True).data)

    serializer = ChatSessionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)

    if request.method == 'GET':
        return Response(ChatSessionDetailSerializer(session).data)

    session.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def message_list_create(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)

    if request.method == 'GET':
        return Response(MessageSerializer(session.messages.all(), many=True).data)

    serializer = MessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user_msg = Message.objects.create(
        session=session,
        role='user',
        content=serializer.validated_data['content'],
    )

    history = list(
        session.messages.exclude(pk=user_msg.pk)
        .order_by('-created_at')[:10]
        .values('role', 'content')
    )
    history.reverse()

    try:
        result = get_response(user_msg.content, history)
    except AIServiceError as exc:
        user_msg.delete()
        return Response({'error': str(exc)}, status=exc.status_code)

    ai_msg = Message.objects.create(
        session=session,
        role='assistant',
        content=result['message'],
        sources=result['sources'],
    )

    # Auto-title the session from the first user message
    if not session.title:
        session.title = user_msg.content[:80]
        session.save(update_fields=['title', 'updated_at'])

    return Response({
        'user': MessageSerializer(user_msg).data,
        'assistant': MessageSerializer(ai_msg).data,
    }, status=status.HTTP_201_CREATED)
