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
from pulumi_kubernetes.core.v1 import ContainerArgs, PodSpecArgs, PodTemplateSpecArgs
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.core.v1 import Namespace, Service
from pulumi_kubernetes.storage.v1 import StorageClass, StorageClassArgs
import efs_eks
import airbyte
import postgresql
import dagster

config = pulumi.Config()
components = config.require_object("components")
stack = pulumi.get_stack()
org = config.require("org")

resources = {"components": components}

# Create namespace for components
resources["namespace"] = Namespace("antares")
pulumi.export("namespace", resources["namespace"].metadata["name"])

# TODO check if the stack exists - it might not
# TODO handle azure & GCP
aws_stack_ref = pulumi.StackReference(f"{org}/antares-idl-aws/{stack}")
resources["aws_stack_ref"] = aws_stack_ref

if components["efs-eks"]:
    efs_eks.configure_efs_storage(resources)

if components["postgresql"]:
    postgresql.deploy_postgresql(resources)

if components["airbyte"]:
    airbyte.deploy_airbyte(resources)

if components["dagster"]:
    dagster.deploy_dagster(resources)
