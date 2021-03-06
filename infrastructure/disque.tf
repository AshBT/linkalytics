resource "google_compute_instance" "disque-node" {
  name          = "disque-${count.index}"
  description   = "The VM hosting a disque server"
  machine_type  = "n1-standard-1"
  zone          = "us-central1-b"
  tags          = ["memex", "linkalytics", "disque", "server"]

  disk {
      image = "debian-8-jessie-v20150915"
      size  = 100 # for disque persistence
  }

  metadata {
    sshKeys = "ansible:${file("keys/gce.pub")}"
  }

  network_interface {
      network = "default"
      access_config {}
  }

  count = 3
}
