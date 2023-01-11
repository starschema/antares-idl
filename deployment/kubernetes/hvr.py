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
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from pulumi_kubernetes.core.v1 import (
    ContainerArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
    Service,
    ServiceSpecArgs,
    ServicePortArgs,
)
from antares_common.resources import resources, component_enabled
from antares_common.config import config


def deploy():

    app_labels = {"app": "hvr", "app_type": "ingestion"}

    hvr_http_port = config.get("/hvr/port", "4340")

    if component_enabled("postgresql"):
        hvr_env = [
            {"name": "HVR_HTTP_PORT", "value": hvr_http_port},
            {"name": "HVR_REPO_CLASS", "value": "postgresql"},
            {
                "name": "HVR_DB_HOST",
                "value": "postgresql",
            },
            {
                "name": "HVR_DB_PORT",
                "value": "5432",
            },
            {"name": "HVR_DB_NAME", "value": "hvr"},
            {
                "name": "HVR_DB_USERNAME",
                "value": resources["postgresql"].values["auth"]["username"],
            },
            {
                "name": "HVR_DB_PASSWORD",
                "value": resources["postgresql"].values["auth"]["password"],
            },
        ]

    else:
        hvr_env = []

    hvr_deployment = Deployment(
        "hvr-deployment",
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
                            name="hvr",
                            image=resources["aws_stack_ref"].get_output(
                                "hvr-full-image-name"
                            ),
                            # command=["sleep"],
                            # args=["1000000"],
                            volume_mounts=[
                                {
                                    "name": "hvr-license",
                                    "mountPath": "/hvr/hvr_home/license",
                                }
                            ],
                            env=hvr_env,
                        )
                    ],
                    volumes=[
                        {
                            "name": "hvr-license",
                            "secret": {
                                "secretName": "hvr-license",
                                "items": [{"key": "license", "path": "hvr.lic"}],
                            },
                        }
                    ],
                ),
            ),
        ),
        opts=pulumi.ResourceOptions(depends_on=[resources["postgresql"]]),
    )

    resources["hvr-deployment"] = hvr_deployment

    service = Service(
        "hvr-service",
        metadata=ObjectMetaArgs(
            namespace=resources["namespace"].metadata["name"],
            labels=app_labels,
        ),
        spec=ServiceSpecArgs(
            ports=[
                ServicePortArgs(
                    port=int(hvr_http_port),
                    protocol="TCP",
                    target_port=int(hvr_http_port),
                )
            ],
            selector=app_labels,
            session_affinity="None",
            type="ClusterIP",
        ),
        opts=pulumi.ResourceOptions(depends_on=[hvr_deployment]),
    )

    resources["hvr-service"] = service
