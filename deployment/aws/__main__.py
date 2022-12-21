"""An AWS Python Pulumi program"""

import pulumi
import json
import pulumi_aws as aws


with open("iam-policy-efs.json") as f:
    policy_doc = json.load(f)

eks_efs_policy = aws.iam.Policy("eks-efs-policy", path="/", policy=policy_doc)


efs_extra_opts = {"availability_zone_name": "eu-central-1b"}

antares_k8s_efs = aws.efs.FileSystem(
    "antares-efs",
    tags={"Framework": "antares", "Maintainer": "tfoldi", "App": "antares"},
    encrypted=True,
    **efs_extra_opts
)

pulumi.export("k8s_efs_id", antares_k8s_efs.id)

vpc = aws.ec2.Vpc.get(
    "k8s_vpc",
    "vpc-0784ff9e77fe41f8c",
    opts=pulumi.ResourceOptions(retain_on_delete=True),
)
pulumi.export("k8s_vpc_id", vpc.id)

allow_efs = aws.ec2.SecurityGroup(
    "allow-efs",
    description="Allow EFS inbound traffic",
    vpc_id=vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            description="TLS from VPC",
            from_port=2049,
            to_port=2049,
            protocol="tcp",
            cidr_blocks=["0.0.0.0/0"],
            ipv6_cidr_blocks=["::/0"],
        )
    ],
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"],
            ipv6_cidr_blocks=["::/0"],
        )
    ],
    tags={
        "Name": "allow_tls",
    },
)


subnet_id = "subnet-0b113b94913ccc494"

efs_mount_target = aws.efs.MountTarget(
    "eks-mount-target",
    file_system_id=antares_k8s_efs.id,
    subnet_id=subnet_id,
    security_groups=[allow_efs.id],
)
