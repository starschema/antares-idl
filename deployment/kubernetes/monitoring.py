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
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.core.v1 import Namespace

from antares_common.resources import resources, component_enabled
from antares_common.config import config


def deploy():
    if config["components"]["efs-eks"][:]:
        storage_class = resources["efs_storage_class"].metadata["name"]
    else:
        storage_class = config.get("/monitoring/storage-class", "")

    monitoring_namespace = Namespace(
        "antares-monitoring-ns",
        metadata=ObjectMetaArgs(
            name=f"antares-{config.stack}-monitoring",
            labels={**config.get("labels", {})},
        ),
    )

    resources["monitoring-namespace"] = monitoring_namespace

    monitoring_release = Release(
        "monitoring-release",
        ReleaseArgs(
            chart="kube-prometheus-stack",
            name="monitoring",
            repository_opts=RepositoryOptsArgs(
                repo="https://prometheus-community.github.io/helm-charts",
            ),
            namespace=monitoring_namespace.metadata["name"],
            create_namespace=False,
            values=config.get("/monitoring/helm-value", {}),
        ),
        opts=pulumi.ResourceOptions(depends_on=[monitoring_namespace]),
    )

    resources["monitoring"] = monitoring_release

    return
