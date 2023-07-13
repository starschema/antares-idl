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
from pulumi_kubernetes.helm.v3 import (
    Release,
    ReleaseArgs,
    RepositoryOptsArgs,
)
from pulumi_kubernetes.core.v1 import Secret, SecretInitArgs
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from antares_common.resources import resources, component_enabled
from antares_common.config import config


def deploy():
    grafana_helm_values = {"securityContext": {"runAsUser": 1000, "runAsGroup": 1000}}

    if component_enabled("efs-eks"):
        grafana_helm_values["persistence"] = {
            "enabled": True,
            "storageClass": "efs-sc-user-1000",
            "accessModes": ["ReadWriteMany"],
        }

    admin_password_secret = Secret(
        "grafana-admin",
        SecretInitArgs(
            string_data={
                "admin-password": config.get("/grafana/admin-password", "antares12"),
                "admin-user": "admin",
            },
            metadata=ObjectMetaArgs(
                namespace=resources["namespace"].metadata["name"],
                name="grafana-admin",
            ),
        ),
    )

    resources["grafana-admin-password"] = admin_password_secret
    grafana_helm_values["admin"] = {
        "existingSecret": "grafana-admin",
    }

    if component_enabled("influxdb2"):
        # TODO: append to existing datasources.yaml if exists
        grafana_helm_values["datasources"] = {
            "datasources.yaml": {
                "apiVersion": 1,
                "datasources": [
                    {
                        "name": "InfluxDB",
                        "type": "influxdb",
                        "access": "proxy",
                        "url": "http://influxdb2:80",
                        "jsonData": {
                            "version": "Flux",
                            "organization": config.get(
                                "/influxdb2/helm-values/adminUser/organization"
                            ),
                            "defaultBucket": config.get(
                                "/influxdb2/helm-values/adminUser/bucket", "default"
                            ),
                            "tlsSkipVerify": True,
                        },
                        "secureJsonData": {
                            "token": config.get(
                                "/influxdb2/helm-values/adminUser/token"
                            )
                        },
                    }
                ],
            }
        }

    grafana_release = Release(
        "grafana",
        ReleaseArgs(
            chart="grafana",
            name="grafana",
            repository_opts=RepositoryOptsArgs(
                repo="https://grafana.github.io/helm-charts",
            ),
            namespace=resources["namespace"].metadata["name"],
            values={
                **grafana_helm_values,
                **(config.get("/grafana/helm-values", {})),
            },
        ),
        opts=pulumi.ResourceOptions(depends_on=[resources["grafana-admin-password"]]),
    )

    resources["grafana"] = grafana_release

    return
