variable "ovh_region" {
  description = "Le DC OVH dans lequel démarrer les runners"
  type = string
  validation {
    condition     = contains(["GRA5", "GRA11", "SBG5"], var.ovh_region)
    error_message = "Seulement GRA5, GRA11 et SBG5 sont supportées pour var.ovh_region."
  }
}

variable "gitlab_runner_token" {
  description = "Le registration token Gitlab"
  type = string
  default = "agggXo8oMS7s9DKeSMBJ"
}
variable "nb_instances" {
  description = "Le nombre de runners à lancer"
  type = number
  default = 2
}
variable "name" {
  description = "Nom de base de l'instance gitlab-runner"
  type        = string
  default = "runner"
}

variable "flavor" {
  description = "Nom de la flavor de l'instance"
  type        = string
  default     = "b2-7"
}
