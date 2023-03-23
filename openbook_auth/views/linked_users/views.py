from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from openbook_auth.views.linked_users.serializers import (
    GetLinkedUsersSerializer,
    SearchLinkedUsersSerializer,
    LinkedUsersUserSerializer,
)


class LinkedUsers(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        query_params = request.query_params.dict()
        serializer = GetLinkedUsersSerializer(data=query_params)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        count = data.get("count", 10)
        max_date_joined = data.get("max_date_joined")
        with_community = data.get("with_community")

        user = request.user
        users = user.get_linked_users(max_date_joined=max_date_joined).order_by("-date_joined")[:count]

        users_serializer = LinkedUsersUserSerializer(
            users,
            many=True,
            context={"request": request, "communities_names": [with_community]},
        )

        return Response(users_serializer.data, status=status.HTTP_200_OK)


class SearchLinkedUsers(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        query_params = request.query_params.dict()
        serializer = SearchLinkedUsersSerializer(data=query_params)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        count = data.get("count", 10)
        query = data.get("query")
        with_community = data.get("with_community")

        user = request.user
        users = user.search_linked_users_with_query(query=query)[:count]

        users_serializer = LinkedUsersUserSerializer(
            users,
            many=True,
            context={"request": request, "communities_names": [with_community]},
        )

        return Response(users_serializer.data, status=status.HTTP_200_OK)
