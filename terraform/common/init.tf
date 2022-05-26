terraform {
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
  region = "europe-west3"
}

provider "google-beta" {
  region = "europe-west3"
}
