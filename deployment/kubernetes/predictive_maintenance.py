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
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from pulumi_kubernetes.core.v1 import (
    ContainerArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
)
from antares_common.resources import resources, component_enabled
from antares_common.config import config


def deploy():
    app_labels = {"app": "predictive_maintenance", "app_type": "ingestion"}

    if component_enabled("emqx"):
        predictive_maintenance_env = [
            {"name": "MQTT_PORT", "value": "1883"},
            {"name": "MQTT_HOST", "value": "emqx-ee"},
        ]
    else:
        predictive_maintenance_env = []

    if component_enabled("influxdb2"):
        predictive_maintenance_env = predictive_maintenance_env + [
            {
                "name": "INFLUX_TOKEN",
                "value": config.get("/influxdb2/helm-values/adminUser/token", ""),
            },
            {
                "name": "INFLUX_ORG",
                "value": config.get(
                    "/influxdb2/helm-values/adminUser/organization", ""
                ),
            },
            {
                "name": "INFLUX_URL",
                "value": config.get("/influxdb2/url", "http://influxdb2"),
            },
            {"name": "INFLUX_PORT", "value": "80"},
            {
                "name": "INFLUX_BUCKET",
                "value": config.get(
                    "/influxdb2/helm-values/adminUser/bucket", "default"
                ),
            },
        ]

    predictive_maintenance_env = predictive_maintenance_env + config.get(
        "/predictive-maintenance/env", []
    )

    docker_image = config.get("/predictive-maintenance/docker-image")

    if not docker_image:
        docker_image = resources[f"{config.get('/cloud/type')}_stack_ref"].get_output(
            "predictive_maintenance-full-image-name"
        )

    for container in ["predict", "load"]:
        deployment = Deployment(
            f"pred-maint-{container}",
            metadata=ObjectMetaArgs(
                namespace=resources["namespace"].metadata["name"],
                labels={**app_labels, **config.get("labels", {})},
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(match_labels=app_labels),
                replicas=1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(
                        labels=app_labels,
                        namespace=resources["namespace"].metadata["name"],
                    ),
                    spec=PodSpecArgs(
                        containers=[
                            ContainerArgs(
                                name="pred-maint",
                                image=docker_image,
                                env=predictive_maintenance_env
                                + [{"name": "LOAD_MODEL", "value": container}],
                                env_from=config.get(
                                    "/predictive-maintenance/env-from", []
                                ),
                                resources=config.get(
                                    "/predictive_maintenance/resources",
                                    {
                                        "requests": {
                                            "cpu": "20m",
                                            "memory": "128Mi",
                                            "ephemeral-storage": "10Mi",
                                        }
                                    },
                                ),
                            )
                        ],
                    ),
                ),
            ),
            opts=pulumi.ResourceOptions(),
        )

        resources["pred-maint-datagen-deployment"] = deployment

    return
