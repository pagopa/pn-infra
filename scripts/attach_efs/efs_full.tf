variable "security_group" {}
variable "vpc" {}

data "aws_subnet_ids" "subnets" {
  vpc_id = "${var.vpc}"
}


resource "aws_efs_file_system" "efs" {
   creation_token = "efs"
   performance_mode = "generalPurpose"
   throughput_mode = "bursting"
   encrypted = "true"
 tags = {
     Name = "EFS"
   }
 }

 resource "aws_efs_mount_target" "efs" {
  for_each = data.aws_subnet_ids.subnets.ids
  file_system_id = aws_efs_file_system.efs.id
  subnet_id = each.value
  security_groups = ["${var.security_group}"]

}

 resource "aws_efs_access_point" "efs_ap" {
  file_system_id = aws_efs_file_system.efs.id
  root_directory {
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = 0755
    }
    path = "/diagnostics"
  }
}
