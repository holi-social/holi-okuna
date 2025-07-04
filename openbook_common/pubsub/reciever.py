from google.cloud import pubsub_v1

from openbook import settings

project_id = settings.GOOGLE_CLOUD_PROJECT_ID
# endpoint = "https://my-test-project.appspot.com/push"
# topic_id = "your-topic-id"
# subscription_id = "your-subscription-id"


publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()

topic_path = publisher.topic_path(project_id, topic_id)
subscription_path = subscriber.subscription_path(project_id, subscription_id)
dead_letter_topic_path = publisher.topic_path(project_id, dead_letter_topic_id)

with subscriber:
    request = {
        "name": subscription_path,
        "topic": topic_path,
    }
    subscription = subscriber.create_subscription(request)

print(f"Subscription created: {subscription.name}")
