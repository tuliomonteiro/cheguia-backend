from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
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
        messages = session.messages.all()
        return Response(MessageSerializer(messages, many=True).data)

    serializer = MessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # Store the user message; AI response will be added once OpenAI is wired in
    message = serializer.save(session=session, role='user')
    return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
