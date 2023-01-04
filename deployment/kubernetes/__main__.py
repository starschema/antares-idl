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
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from pulumi_kubernetes.core.v1 import ContainerArgs, PodSpecArgs, PodTemplateSpecArgs
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.core.v1 import Namespace, Service
from pulumi_kubernetes.storage.v1 import StorageClass, StorageClassArgs


currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.insert(0, f"{currentdir}/../../lib")

from antares_common.resources import resources, component_enabled
from antares_common.config import config
import efs_eks
import airbyte
import postgresql
import dagster
import secrets


# Create namespace for components
resources["namespace"] = Namespace("antares")
pulumi.export("namespace", resources["namespace"].metadata["name"])


if config.get("secrets"):
    secrets.deploy_secrets()

if component_enabled("efs-eks"):
    # TODO check if the stack exists - it might not
    # TODO handle azure & GCP
    resources["aws_stack_ref"] = pulumi.StackReference(
        f"{config.org}/antares-idl-aws/{config.stack}"
    )
    efs_eks.configure_efs_storage()

if component_enabled("postgresql"):
    postgresql.deploy_postgresql()

if component_enabled("airbyte"):
    airbyte.deploy_airbyte()

if component_enabled("dagster"):
    dagster.deploy_dagster()
