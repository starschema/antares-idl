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
    app_labels = {"app": "lm_sensors", "app_type": "ingestion"}

    if component_enabled("emqx"):
        lm_sensors_env = [
            {"name": "MQTT_PORT", "value": "1883"},
            {"name": "MQTT_HOST", "value": "emqx-ee"},
        ]
    else:
        lm_sensors_env = []

    lm_sensors_env = lm_sensors_env + config.get("/lm-sensors/env", [])

    docker_image = config.get("/lm-sensors/docker-image")

    if not docker_image:
        docker_image = resources[f"{config.get('/cloud/type')}_stack_ref"].get_output(
            "lm-sensor-sparkplug-full-image-name"
        )

    lm_sensors_deployment = Deployment(
        "lm-sensors-deployment",
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
                            name="lm-sensors",
                            image=docker_image,
                            env=lm_sensors_env,
                            env_from=config.get("/lm-sensors/env-from", []),
                        )
                    ],
                ),
            ),
        ),
        opts=pulumi.ResourceOptions(),
    )

    resources["lm-sensors-deployment"] = lm_sensors_deployment

    return
