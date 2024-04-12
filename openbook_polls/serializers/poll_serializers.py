from rest_framework import serializers

from django.conf import settings


class CreateQuestionSerializer(serializers.Serializer):
    question_text = serializers.CharField(
        max_length=200,
        required=True,
        allow_blank=False
    )
    # choice_text = serializers.CharField(
    #     max_length=200,
    #     required=False,
    #     allow_blank=False
    # )
    # votes = serializers.IntegerField(
    #     required=False
    # )
    # creator=serializers.UUIDField(
    #     required=True
    # )

    # creator = PostCreatorField(
    #      post_creator_serializer=CommonPublicUserSerializer,
    #      community_membership_serializer=CommunityMembershipSerializer,
    #      )

# class EditQuestionSerializer(serializers.Serializer):
#     question_id = serializers.UUIDField(
#         validators=[question_id_exists],
#         required=True,
#     )
#     question_text = serializers.CharField(
#         max_length=200,
#         required=False,
#         allow_blank=False,
#         validators=question_text_validators,
#     )
#     #visibility = serializers.ChoiceField(VisibilityType.choices)
#     is_draft = serializers.BooleanField(default=False)