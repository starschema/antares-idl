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
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.core.v1 import ServiceAccount
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.storage.v1 import StorageClass
from antares_common.resources import resources


def deploy():
    efs_service_account = ServiceAccount(
        "efs-csi-controller-sa",
        metadata=ObjectMetaArgs(
            labels={"app.kubernetes.io/name": "aws-efs-csi-driver"},
            name="efs-csi-controller-sa",
            namespace="kube-system",
            annotations={
                "eks.amazonaws.com/role-arn": resources["aws_stack_ref"].get_output(
                    "efs_csi_driver_role_arn"
                ),
            },
        ),
    )

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
                },
            },
        ),
    )

    pulumi.export("aws-efs-csi-driver", aws_efs_csi_driver.status.name)

    efs_storage_class = StorageClass(
        "efs-sc",
        metadata=ObjectMetaArgs(
            name="efs-sc",
        ),
        provisioner="efs.csi.aws.com",
        parameters={
            "provisioningMode": "efs-ap",
            "fileSystemId": resources["aws_stack_ref"].get_output("k8s_efs_id"),
            "directoryPerms": "700",
            "basePath": "/eks_dynamic",
        },
    )

    resources["efs_storage_class"] = efs_storage_class

    postgresql_storage_class = StorageClass(
        "efs-postgres",
        metadata=ObjectMetaArgs(
            name="efs-postgres",
        ),
        provisioner="efs.csi.aws.com",
        parameters={
            "provisioningMode": "efs-ap",
            "fileSystemId": resources["aws_stack_ref"].get_output("k8s_efs_id"),
            "directoryPerms": "700",
            "basePath": "/eks_dynamic",
            "gid": "1001",
            "uid": "1001",
        },
    )

    resources["postgresql_storage_class"] = postgresql_storage_class

    return
