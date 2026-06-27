from rest_framework import serializers
from .models import ChatSession, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'sources', 'created_at']
        read_only_fields = ['id', 'role', 'sources', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'platform', 'created_at', 'updated_at', 'last_message']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        return msg.content[:100] if msg else None


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'platform', 'created_at', 'updated_at', 'messages']
        read_only_fields = ['id', 'created_at', 'updated_at']
