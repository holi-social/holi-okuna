locals {
  # todo gregor: uncomment after infra works on review okuna
  # create_subscription = contains(["staging", "production"], local.environment_type)
}

resource "google_kms_crypto_key_iam_member" "external_data_pubsub_decrypter" {
  crypto_key_id = data.terraform_remote_state.holi_data_pipeline_common_state.outputs.data_pipeline_key
  role          = "roles/cloudkms.cryptoKeyDecrypter"
  member        = "serviceAccount:${data.terraform_remote_state.holi_okuna_common_state.outputs.cloud_run_service_account_email}"
}


resource "google_eventarc_trigger" "external_data_push" {
  # count   = local.create_subscription ? 1 : 0

  name     = random_id.main.hex
  location = local.default_region
  project  = local.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_service.okuna.name
      region  = google_cloud_run_service.okuna.location
      path    = "/pubsub/subscription/${local.external_data_topic_name}/"
    }

    network_config {
      network_attachment = data.terraform_remote_state.holi_infra_state.outputs.vpc_access_connector_name
    }
  }

  transport {
    pubsub {
      topic = local.external_data_topic_id
    }
  }

  service_account = data.terraform_remote_state.holi_okuna_common_state.outputs.cloud_run_service_account_email
}

resource "google_monitoring_alert_policy" "external_data_sub_unacked_messages_alert" {
  # count   = local.create_subscription ? 1 : 0

  project      = local.project_id
  display_name = "External Data: Unacked Messages Alert / subscription_name='${google_eventarc_trigger.external_data_push.transport.pubsub.subscription}'"
  combiner     = "OR"
  conditions {
    display_name = "Unacked messages condition"
    condition_prometheus_query_language {
      query    = "rate(pubsub_googleapis_com:subscription_oldest_unacked_message_age{subscription_name='${google_eventarc_trigger.external_data_push.transport.pubsub.subscription}'}[5m]) >= 1"
      duration = "300s"
    }
  }

  alert_strategy {
    auto_close = "300s"
  }

  notification_channels = [
      local.environment_name == "production" ?  local.google_monitoring_slack_notification_production_id : local.google_monitoring_slack_notification_staging_id
  ]

  documentation {
    content   = "Alert triggered when Pub/Sub subscription ('${google_eventarc_trigger.external_data_push.transport.pubsub.subscription}') has unacknowledged messages for more than 5 minutes. Please check the cloud function deployment and logs to see if the subscriber works correctly."
    mime_type = "text/markdown"
  }
}
