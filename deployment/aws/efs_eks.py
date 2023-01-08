"""
MIT License

Copyright (c) 2022 HCLTech

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import pulumi
import json
import pulumi_aws as aws
from antares_common.resources import resources
from antares_common.config import config


def deploy_efs():

    # First of all get the necessary information about the EKS cluster
    eks_cluster = aws.eks.Cluster.get(
        "eks-cluster",
        config["/efs-eks/eks_cluster_name"][:],
        opts=pulumi.ResourceOptions(retain_on_delete=True),
    )
    eks_oidc_issuer = (
        eks_cluster.identities[0]
        .oidcs[0]
        .issuer.apply(lambda s: s.replace("https://", ""))
    )

    # The policy will allow the Amazon EFS driver to interact with the file system.
    with open("iam-policy-efs.json") as f:
        policy_doc = json.load(f)

    eks_efs_policy = aws.iam.Policy("eks-efs-policy", path="/", policy=policy_doc)

    eks_efs_csi_federation = pulumi.Output.all(
        aws_account_id=resources["aws_account_id"],
        eks_oidc_issuer=eks_oidc_issuer,
    ).apply(
        lambda args: f"arn:aws:iam::{args['aws_account_id']}:oidc-provider/{args['eks_oidc_issuer']}"
    )

    # Create the IAM role, granting the Kubernetes service account the AssumeRoleWithWebIdentity action.
    # This is required to allow the EFS CSI driver to assume the IAM role.
    efs_csi_driver_role = aws.iam.Role(
        "eks-efs-csi-driver",
        assume_role_policy=pulumi.Output.all(
            eks_efs_csi_federation=eks_efs_csi_federation,
            eks_oidc_issuer=eks_oidc_issuer,
        ).apply(
            lambda args: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Federated": "eks-efs-csi-federation"},
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {
                                    "eks_oidc_issuer:sub": "system:serviceaccount:kube-system:efs-csi-controller-sa"
                                }
                            },
                        }
                    ],
                }
            )
            .replace("eks-efs-csi-federation", args["eks_efs_csi_federation"])
            .replace("eks_oidc_issuer", args["eks_oidc_issuer"])
        ),
    )

    pulumi.export("efs_csi_driver_role_arn", efs_csi_driver_role.arn)

    aws.iam.RolePolicyAttachment(
        "attach-eks-efs-csi-driver",
        role=efs_csi_driver_role.name,
        policy_arn=eks_efs_policy.arn,
    )

    # Create the EFS file system
    if config.get("/efs-eks/availability_zone_name"):
        efs_extra_opts = {
            "availability_zone_name": config["/efs-eks/availability_zone_name"][:]
        }
    else:
        efs_extra_opts = {}

    antares_k8s_efs = aws.efs.FileSystem(
        "antares-efs",
        tags={"Framework": "antares", "Maintainer": "tfoldi", "App": "antares"},
        encrypted=True,
        **efs_extra_opts,
    )

    pulumi.export("k8s_efs_id", antares_k8s_efs.id)

    vpc = aws.ec2.Vpc.get(
        "k8s_vpc",
        eks_cluster.vpc_config.vpc_id,
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

    def create_mount_for_subnets(vpc_config):
        # TODO: pick one subnet per supported AZ
        for subnet_id in vpc_config.subnet_ids[:1]:
            aws.efs.MountTarget(
                f"eks-mount-target-{subnet_id}",
                file_system_id=antares_k8s_efs.id,
                subnet_id=subnet_id,
                security_groups=[allow_efs.id],
            )

    eks_cluster.vpc_config.apply(create_mount_for_subnets)
