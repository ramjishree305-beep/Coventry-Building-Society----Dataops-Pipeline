terraform {
  required_version = ">= 1.5"
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

variable "db_password" {
  description = "Postgres password. Set with: export TF_VAR_db_password=..."
  type        = string
  sensitive   = true
}

locals {
  project   = "dataops"
  repo_root = abspath("${path.module}/..")
}

resource "docker_network" "net" {
  name = "${local.project}-net"
}

resource "docker_image" "postgres" {
  name = "postgres:16"
}

resource "docker_volume" "pgdata" {
  name = "${local.project}-pgdata"
}

resource "docker_container" "postgres" {
  name  = "${local.project}-postgres"
  image = docker_image.postgres.image_id
  env = [
    "POSTGRES_DB=analytics",
    "POSTGRES_USER=pipeline",
    "POSTGRES_PASSWORD=${var.db_password}",
  ]
  ports {
    internal = 5432
    external = 5432
  }
  volumes {
    volume_name    = docker_volume.pgdata.name
    container_path = "/var/lib/postgresql/data"
  }
  networks_advanced {
    name    = docker_network.net.name
    aliases = ["postgres"]
  }
  healthcheck {
    test     = ["CMD-SHELL", "pg_isready -U pipeline -d analytics"]
    interval = "5s"
    retries  = 10
  }
  wait = true
}

resource "docker_image" "pipeline" {
  name = "${local.project}-pipeline:latest"
  build {
    context = local.repo_root
  }
}

resource "docker_container" "pipeline" {
  name     = "${local.project}-pipeline"
  image    = docker_image.pipeline.image_id
  must_run = false
  env = [
    "DB_HOST=postgres",
    "DB_PASSWORD=${var.db_password}",
  ]
  volumes {
    host_path      = "${local.repo_root}/data"
    container_path = "/app/data"
  }
  volumes {
    host_path      = "${local.repo_root}/logs"
    container_path = "/app/logs"
  }
  networks_advanced {
    name = docker_network.net.name
  }
  depends_on = [docker_container.postgres]
}

output "postgres" {
  value = "psql -h localhost -U pipeline -d analytics   (password = TF_VAR_db_password)"
}

output "pipeline_logs" {
  value = "docker logs ${docker_container.pipeline.name}"
}

output "rerun_pipeline" {
  value = "docker start -a ${docker_container.pipeline.name}"
}
