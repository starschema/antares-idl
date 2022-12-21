"""A Kubernetes Python Pulumi program"""

import pulumi
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from pulumi_kubernetes.core.v1 import ContainerArgs, PodSpecArgs, PodTemplateSpecArgs
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.core.v1 import Namespace, Service
from pulumi_kubernetes.storage.v1 import StorageClass, StorageClassArgs

config = pulumi.Config()
stack = pulumi.get_stack()
org = config.require("org")

aws_stack_ref = pulumi.StackReference(f"{org}/antares-idl-aws/{stack}")

aws_efs_csi_driver = Release(
    "aws-efs-csi-driver",
    ReleaseArgs(
        chart="aws-efs-csi-driver",
        name="aws-efs-csi-driver",
        repository_opts=RepositoryOptsArgs(
            repo="https://kubernetes-sigs.github.io/aws-efs-csi-driver/",
        ),
        namespace="kube-system",
        values={
            "image": {
                "repository": "602401143452.dkr.ecr.eu-central-1.amazonaws.com/eks/aws-efs-csi-driver",
            },
            "controller": {
                "serviceAccount": {
                    "create": False,
                    "name": "efs-csi-controller-sa",
                }
            }
        },
    ),
)

status = aws_efs_csi_driver.status
pulumi.export("aws-efs-csi-driver", aws_efs_csi_driver.status.name)

efs_storage_class = StorageClass("efs-sc",
                                 metadata=ObjectMetaArgs(
                                     name= "efs-sc",
                                 ),
                                 provisioner="efs.csi.aws.com",
                                 parameters={
                                     "provisioningMode": "efs-ap",
                                     "fileSystemId": aws_stack_ref.get_output("url"),
                                     "directoryPerms": "700",
                                     "basePath": "/eks_dynamic",
                                 },
                                 )
