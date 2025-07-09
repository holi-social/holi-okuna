resource "google_pubsub_subscription" "external_data_subscription" {
  project = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  name    = random_id.main.hex
  topic   = local.environment_name == "production" ? data.terraform_remote_state.holi_data_pipeline_common_state.outputs.google_pubsub_topic_external_data_production : data.terraform_remote_state.holi_data_pipeline_common_state.outputs.google_pubsub_topic_external_data_staging

  enable_message_ordering = true

  expiration_policy {
    ttl = "" # never expire
  }

  push_config {
    push_endpoint = "https://${local.dns_name}/pubsub/push/"

    oidc_token {
      audience = "okuna-pubsub-push"
      service_account_email = data.terraform_remote_state.holi_okuna_common_state.outputs.cloud_run_service_account_email
    }
  }
}


resource "google_monitoring_alert_policy" "external_data_sub_unacked_messages_alert" {
  project      = data.terraform_remote_state.holi_infra_state.outputs.shared_project_id
  display_name = "External Data -> Okuna: Unacked Messages Alert (${local.environment_name}) / subscription_id='${google_pubsub_subscription.external_data_subscription.name}'"
  combiner     = "OR"
  conditions {
    display_name = "Unacked messages condition"
    condition_prometheus_query_language {
      query    = "rate(pubsub_googleapis_com:subscription_oldest_unacked_message_age{subscription_id='${google_pubsub_subscription.external_data_subscription.name}'}[5m]) >= 1"
      duration = "300s"
    }
  }

  alert_strategy {
    auto_close = "300s"
  }

  notification_channels = [local.environment_name == "production" ? data.terraform_remote_state.holi_infra_monitoring_state.outputs.monitoring_notification_channel_slack_production_id : data.terraform_remote_state.holi_infra_monitoring_state.outputs.monitoring_notification_channel_slack_staging_id]

  documentation {
    content   = "Alert triggered when Pub/Sub subscription(s) (subscription_id='${google_pubsub_subscription.external_data_subscription.name}') have unacknowledged messages for more than 5 minutes. Please check the cloud function deployment and logs to see if the subscriber works correctly."
    mime_type = "text/markdown"
  }
}

output "google_pubsub_external_data_subscription_id" {
  value = google_pubsub_subscription.external_data_subscription.id
}
