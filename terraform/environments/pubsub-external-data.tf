resource "google_kms_crypto_key_iam_member" "external_data_pubsub_decrypter" {
  crypto_key_id = data.terraform_remote_state.holi_data_pipeline_common_state.outputs.data_pipeline_key
  role          = "roles/cloudkms.cryptoKeyDecrypter"
  member        = "serviceAccount:${data.terraform_remote_state.holi_okuna_common_state.outputs.cloud_run_service_account_email}"
}


resource "google_eventarc_trigger" "external_data_push" {

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
