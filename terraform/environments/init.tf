terraform {
  # allow the lowest common version across all projects, so that the current CI docker image version suits all projects
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.17.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "7.15.0"
    }
  }
  backend "gcs" {
    bucket = "holi-shared-terraform-state"
    prefix = "okuna-environments"
  }
}

data "terraform_remote_state" "holi_infra_state" {
  backend = "gcs"
  config = {
    bucket = "holi-shared-terraform-state"
    prefix = "infra"
  }
}

data "terraform_remote_state" "holi_okuna_common_state" {
  backend = "gcs"
  config = {
    bucket = "holi-shared-terraform-state"
    prefix = "okuna-common"
  }
}

data "terraform_remote_state" "holi_infra_monitoring_state" {
  backend = "gcs"
  config = {
    bucket = "holi-shared-terraform-state"
    prefix = "infra-monitoring"
  }
}

data "terraform_remote_state" "holi_data_pipeline_common_state" {
  backend = "gcs"
  config = {
    bucket = "holi-shared-terraform-state"
    prefix = "data-pipeline-common"
  }
}

data "terraform_remote_state" "rewards" {
  backend = "gcs"
  config = {
    bucket = "holi-shared-terraform-state"
    prefix = "rewards-environments"
  }
  workspace = local.environment_name == "production" ? "production" : "staging"
}

# provider google including beta features
provider "google" {
  region = local.default_region
}

provider "google-beta" {
  region = local.default_region
}
