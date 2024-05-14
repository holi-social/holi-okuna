from rest_framework import serializers


class CreatePollSerializer(serializers.Serializer):
    question_text = serializers.CharField(max_length=200, required=True, allow_blank=False)
