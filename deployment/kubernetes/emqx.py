"""
MIT License

Copyright (c) 2023 HCLTech

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
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.apiextensions import CustomResource
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.core.v1 import (
    Pod,
    ContainerArgs,
    PodSpecArgs,
)

from antares_common.resources import resources, component_enabled
from antares_common.config import config


def deploy():
    if not component_enabled("cert-manager"):
        raise Exception("cert-manager is required for emqx")

    emqx_release = Release(
        "emqx",
        ReleaseArgs(
            chart="emqx-operator",
            name="emqx",
            repository_opts=RepositoryOptsArgs(
                repo="https://repos.emqx.io/charts",
            ),
            namespace="emqx-operator-system",
            create_namespace=True,
            values={},
        ),
        opts=pulumi.ResourceOptions(
            depends_on=[resources["cert-manager"]]
            if component_enabled("cert-manager")
            else []
        ),
    )

    resources["emqx"] = emqx_release

    emqx_ee = CustomResource(
        "emqx-ee",
        api_version="apps.emqx.io/v1beta4",
        kind="EmqxEnterprise",
        metadata=ObjectMetaArgs(
            name="emqx-ee",
            namespace=resources["namespace"].metadata["name"],
        ),
        spec={
            **(
                {
                    "license": config.get("/emqx/license"),
                }
                if config.get("/emqx/license", "")
                else {}
            ),
            "replicas": config.get("/emqx/replicas", 1),
            "volumeClaimTemplates": config.get("/emqx/persistent-volume", {}),
            "template": {
                "spec": {
                    "emqxContainer": {
                        "image": {
                            "version": config.get("/emqx/version", "4.4.14"),
                            "repository": "emqx/emqx-ee",
                        },
                        "emqxConfig": config.get("/emqx/emqx-config", {}),
                        "emqxACL": config.get("/emqx/emqx-acl", []),
                    }
                }
                # TODO: set up emqx persistency storage class
            },
        },
        opts=pulumi.ResourceOptions(depends_on=[emqx_release]),
    )

    resources["emqx-ee"] = emqx_ee

    if config.get("/emqx/import-file", False):
        emqx_ee_importer = (
            Pod(
                "emqx-ee-import",
                metadata=ObjectMetaArgs(
                    name="emqx-ee-import-backup",
                    namespace=resources["namespace"].metadata["name"],
                ),
                spec=PodSpecArgs(
                    restart_policy="Never",
                    containers=[
                        ContainerArgs(
                            name="emqx-ee-sync",
                            image="alpine/curl",
                            image_pull_policy="IfNotPresent",
                            command=["/bin/sh"],
                            # TODO: ensure 8081 is the correct port, can be overridem from config
                            args=[
                                "-c",
                                f"""
                                # Wait for the emqx cluster to be ready
                                while ! nc -z emqx-ee 8081; do   
                                    sleep 1
                                done

                                # Download the export file
                                curl -o /tmp/export.json {config.get("/emqx/import-file")} && 
                                # Import the data into the cluster
                                curl -i --basic -u admin:public -X POST "http://emqx-ee:8081/api/v4/data/import" -d@/tmp/export.json""",
                            ],
                            working_dir="/tmp",
                        )
                    ],
                ),
                opts=pulumi.ResourceOptions(depends_on=[emqx_ee]),
            ),
        )

    return
