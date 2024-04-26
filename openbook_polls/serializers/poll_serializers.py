from rest_framework import serializers

from django.conf import settings


class CreateQuestionSerializer(serializers.Serializer):
    question_text = serializers.CharField(
        max_length=200,
        required=True,
        allow_blank=False
    )