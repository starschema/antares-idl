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

import os
import sys
import inspect
import pulumi
from pulumi_kubernetes.meta.v1 import ObjectMetaArgs
from pulumi_kubernetes.core.v1 import Namespace


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, f"{currentdir}/../../lib")

from antares_common.resources import resources, component_enabled
from antares_common.config import config
import secrets
import config_maps
import efs_eks
import dagster
import airbyte
import hvr
import postgresql
import emqx
import influxdb2
import grafana
import cert_manager
import growatt
import lm_sensors
import monitoring

# Create namespace for components
resources["namespace"] = Namespace(
    "antares",
    metadata=ObjectMetaArgs(
        name=f"antares-{config.stack}",
        labels={**config.get("labels", {})},
    ),
)
pulumi.export("namespace", resources["namespace"].metadata["name"])


# if we are in the cloud, then let's load the cloud stack stack ref's
if config.get("/cloud/type"):
    resources[f"{config.cloud.type}_stack_ref"] = pulumi.StackReference(
        f"{config.org}/antares-idl-{config.cloud.type}/{config.get('/cloud/upstream-stack',config.stack)}"
    )

if config.get("secrets"):
    secrets.deploy()

if config.get("config_maps"):
    config_maps.deploy()


if component_enabled("efs-eks"):
    efs_eks.deploy()

if component_enabled("cert-manager"):
    cert_manager.deploy()

if component_enabled("monitoring"):
    monitoring.deploy()

if component_enabled("postgresql"):
    postgresql.deploy()

if component_enabled("airbyte"):
    airbyte.deploy()

if component_enabled("hvr"):
    hvr.deploy()

if component_enabled("dagster"):
    dagster.deploy()

if component_enabled("emqx"):
    emqx.deploy()

if component_enabled("influxdb2"):
    influxdb2.deploy()

if component_enabled("grafana"):
    grafana.deploy()

if component_enabled("growatt"):
    growatt.deploy()

if component_enabled("lm-sensors"):
    lm_sensors.deploy()
