terraform {
  backend "gcs" {
    bucket = "holi-shared-terraform-state"
    prefix = "okuna-environments"
  }
}

data "terraform_remote_state" "holi_okuna_common_state" {
  backend = "gcs"
  config = {
    bucket = "holi-shared-terraform-state"
    prefix = "okuna-common"
  }
}

# provider google including beta features
provider "google" {
  region = "europe-west3"
}

provider "google-beta" {
  region = "europe-west3"
}
