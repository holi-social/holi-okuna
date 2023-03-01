from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from openbook_auth.models import to_list_of_dicts
from openbook_common.utils.model_loaders import get_emoji_group_model, get_post_model
from openbook_moderation.permissions import IsNotSuspended
from openbook_posts.views.post_reactions.serializers import (
    GetPostReactionsSerializer,
    GetPostReactionsEmojiCountSerializer,
    PostEmojiCountSerializer,
    PostReactionEmojiGroupSerializer,
    ReactToPostSerializer,
)
from openbook_posts.views.post_reaction.serializers import PostReactionSerializer


class PostReactions(APIView):
    permission_classes = (IsAuthenticated, IsNotSuspended)

    def get(self, request, post_id):
        request_data = self._get_request_data(request, post_id)

        serializer = GetPostReactionsSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        post_id = data.get("post_id")
        emoji_id = data.get("emoji_id")
        max_id = data.get("max_id")
        count = data.get("count", 10)

        user = request.user

        post_reactions = user.get_reactions_for_post_with_id(
            post_id=post_id, max_id=max_id, emoji_id=emoji_id
        ).order_by("-created")[:count]

        post_reactions_serializer = PostReactionSerializer(post_reactions, many=True, context={"request": request})

        return Response(post_reactions_serializer.data, status=status.HTTP_200_OK)

    def put(self, request, post_id):
        request_data = self._get_request_data(request, post_id)

        serializer = ReactToPostSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        reaction_type = data.get("reaction_type")
        post_id = data.get("post_id")

        user = request.user

        with transaction.atomic():
            post_reaction = user.react_to_post_with_id(
                post_id=post_id,
                reaction_type=reaction_type,
            )

        post_reaction_serializer = PostReactionSerializer(post_reaction, context={"request": request})
        return Response(post_reaction_serializer.data, status=status.HTTP_201_CREATED)

    def _get_request_data(self, request, post_id):
        request_data = request.data.copy()
        query_params = request.query_params.dict()
        request_data.update(query_params)
        request_data["post_id"] = post_id
        return request_data


class PostReactionsEmojiCount(APIView):
    permission_classes = (IsAuthenticated, IsNotSuspended)

    def get(self, request, post_id):
        request_data = self._get_request_data(request, post_id)

        serializer = GetPostReactionsEmojiCountSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        post_id = data.get("post_id")

        user = request.user

        post_emoji_counts = to_list_of_dicts(
            user.get_reaction_counts_for_post_with_id(post_id), "reaction_type", "count"
        )

        post_reactions_serializer = PostEmojiCountSerializer(
            post_emoji_counts, many=True, context={"request": request}
        )

        return Response(post_reactions_serializer.data, status=status.HTTP_200_OK)

    def _get_request_data(self, request, post_id):
        request_data = request.data.copy()
        query_params = request.query_params.dict()
        request_data.update(query_params)
        request_data["post_id"] = post_id
        return request_data


class PostReactionEmojiGroups(APIView):
    permission_classes = (IsAuthenticated, IsNotSuspended)

    def get(self, request):
        EmojiGroup = get_emoji_group_model()
        emoji_groups = EmojiGroup.objects.filter(is_reaction_group=True).all().order_by("order")
        serializer = PostReactionEmojiGroupSerializer(emoji_groups, many=True, context={"request": request})

        return Response(serializer.data, status=status.HTTP_200_OK)
