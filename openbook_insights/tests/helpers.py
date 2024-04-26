from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema


def get_insight(user, id):
    return async_to_sync(schema.execute)(
        """
        query test($id: UUID!){
            insightById(id: $id) {
                id
                title
                description
                discussions {
                    id
                    question
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "id": str(id),
        },
    )
