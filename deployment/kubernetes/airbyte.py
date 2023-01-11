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

from pulumi_kubernetes.helm.v3 import (
    Release,
    ReleaseArgs,
    RepositoryOptsArgs,
)
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.core.v1 import (
    PersistentVolumeClaim,
    PersistentVolumeClaimSpecArgs,
    Pod,
    ContainerArgs,
    PodSpecArgs,
)
import pulumi

from antares_common.resources import resources, component_enabled
from antares_common.config import config


def deploy():

    if component_enabled("postgresql"):
        airbyte_helm_values = {
            "global": {
                "database": {
                    "secretName": "postgresql",
                    "secretValue": "password",
                    "host": "postgresql",
                }
            },
            "postgresql": {"enabled": False},
            "externalDatabase": {
                "host": "postgresql",
                "user": resources["postgresql"].values["auth"]["username"],
                "database": "airbyte",
                "password": resources["postgresql"].values["auth"]["password"],
            },
        }
        depends_on = [resources["postgresql"]]
    else:
        airbyte_helm_values = {}
        depends_on = []

    airbyte_release = Release(
        "airbyte",
        ReleaseArgs(
            chart="airbyte",
            name="airbyte",
            repository_opts=RepositoryOptsArgs(
                repo="https://airbytehq.github.io/helm-charts",
            ),
            namespace=resources["namespace"].metadata["name"],
            values={**airbyte_helm_values, **(config.get("/airbyte/helm-values", {}))},
        ),
        opts=pulumi.ResourceOptions(depends_on=depends_on),
    )

    resources["airbyte"] = airbyte_release

    airbyte_repo_pvc = PersistentVolumeClaim(
        "airbyte-repository-pvc",
        metadata=ObjectMetaArgs(
            name="airbyte-repository-pvc",
            namespace=resources["namespace"].metadata["name"],
        ),
        spec=PersistentVolumeClaimSpecArgs(
            # TODO: take it from config
            storage_class_name="efs-sc",
            access_modes=["ReadWriteOnce"],
            resources={"requests": {"storage": "20M"}},
        ),
        opts=pulumi.ResourceOptions(depends_on=[airbyte_release]),
    )

    resources["ab_pvc"] = airbyte_repo_pvc

    octavia_sidecar = (
        Pod(
            "airbyte-git-sync",
            metadata=ObjectMetaArgs(
                name="airbyte-git-sync",
                namespace=resources["namespace"].metadata["name"],
            ),
            spec=PodSpecArgs(
                restart_policy="Never",
                volumes=[
                    {
                        "name": "workdir",
                        "persistentVolumeClaim": {
                            "claimName": airbyte_repo_pvc.metadata["name"]
                        },
                    }
                ],
                containers=[
                    ContainerArgs(
                        name="airbyte-octavia",
                        image="airbyte/octavia-cli:0.40.26",
                        image_pull_policy="IfNotPresent",
                        args=[
                            "--airbyte-url",
                            "http://airbyte-airbyte-webapp-svc/",
                            "apply",
                            "--force",
                        ],
                        working_dir="/home/octavia-project/HEAD/airbyte",
                        volume_mounts=[
                            {"name": "workdir", "mountPath": "/home/octavia-project"}
                        ],
                        env_from=[{"secretRef": {"name": "database-credentials"}}],
                    )
                ],
                init_containers=[
                    ContainerArgs(
                        name="airbyte-git-sync",
                        image="k8s.gcr.io/git-sync/git-sync:v3.6.2",
                        image_pull_policy="IfNotPresent",
                        args=[
                            "--one-time",
                            "--root",
                            "/home/octavia-project",
                            "--repo",
                            config.get("/airbyte/repo/url", ""),
                            "--branch",
                            config.get("/airbyte/repo/branch", "main"),
                            "--dest",
                            "HEAD",
                            "--change-permissions",
                            "0777",
                        ],
                        volume_mounts=[
                            {"name": "workdir", "mountPath": "/home/octavia-project"}
                        ],
                        # TODO: env from config
                        env_from=[{"secretRef": {"name": "database-credentials"}}],
                    )
                ],
            ),
            opts=pulumi.ResourceOptions(depends_on=[airbyte_release, airbyte_repo_pvc]),
        ),
    )

    return
