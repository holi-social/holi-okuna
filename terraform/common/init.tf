terraform {
  # allow the lowest common version across all projects, so that the current CI docker image version suits all projects
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.46.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "6.36.1"
    }
  }
  backend "gcs" {
    bucket = "holi-shared-terraform-state"
    prefix = "okuna-common"
  }
}

data "terraform_remote_state" "holi_infra_state" {
  backend = "gcs"
  config = {
    bucket = "holi-shared-terraform-state"
    prefix = "infra"
  }
}

# provider google including beta features
provider "google" {
  region = local.default_region
}

provider "google-beta" {
  region = local.default_region
}
