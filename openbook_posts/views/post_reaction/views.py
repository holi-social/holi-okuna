from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.translation import gettext_lazy as _
from openbook_moderation.permissions import IsNotSuspended
from openbook_posts.views.post_reaction.serializers import DeletePostReactionSerializer


class PostReactionItem(APIView):
    permission_classes = (IsAuthenticated, IsNotSuspended)

    def delete(self, request, post_id, post_reaction_id):
        request_data = self._get_request_data(request, post_id, post_reaction_id)

        serializer = DeletePostReactionSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        post_id = data.get("post_id")
        post_reaction_id = data.get("post_reaction_id")

        user = request.user

        with transaction.atomic():
            user.delete_reaction_with_id_for_post_with_id(
                post_reaction_id=post_reaction_id,
                post_id=post_id,
            )

        return Response({"message": _("Reaction deleted")}, status=status.HTTP_200_OK)

    def _get_request_data(self, request, post_id, post_reaction_id):
        request_data = request.data.copy()
        request_data["post_id"] = post_id
        request_data["post_reaction_id"] = post_reaction_id
        return request_data
