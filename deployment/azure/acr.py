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

import base64
import pulumi
from pulumi import ResourceOptions
import pulumi_docker as docker

from pulumi_azure_native import (
    containerregistry,
    authorization,
)
import pulumi_azuread as azuread

from antares_common.resources import resources, component_enabled
from antares_common.config import config


def deploy():
    prefix = f"antares-{config.stack}"
    subscription_id = authorization.get_client_config().subscription_id

    print(
        f"{prefix}-acr",
    )
    acr_registry = containerregistry.Registry(
        "antares-acr",
        admin_user_enabled=True,
        location=config.get(
            "/acr/location", pulumi.Config("azure-native").require("location")
        ),
        # registry name can only contain alphanumeric characters and no hyphens
        registry_name="antaresAcr",
        resource_group_name=resources["resource-group"].name,
        sku=containerregistry.SkuArgs(
            name=config.get("/acr/sku", "Standard"),
        ),
        tags={
            ## TODO: add tags
        },
    )

    if component_enabled("aks"):
        sp_auth = authorization.RoleAssignment(
            "aks-acr-auth",
            scope=acr_registry.id,
            role_definition_id=f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions/acdd72a7-3385-48ef-bd42-f606fba81ae7",
            principal_id=resources["aks-sp"].id,
            principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
        )

    # Get registry info (creds and endpoint).
    creds = containerregistry.get_registry_credentials_output(
        registry_name=acr_registry.name,
        resource_group_name=resources["resource-group"].name,
    )
    registry_info = docker.ImageRegistry(
        server=acr_registry.login_server,
        username=creds.username,
        password=creds.password,
    )

    # Publish all the images to the registry.
    for container in config.get("/ecr/containers", []):
        image_name = acr_registry.login_server.apply(
            lambda s: f'{s}/{container["name"]}'
        )

        image = docker.Image(
            "hvr-docker-image",
            build=docker.DockerBuild(
                context=f"../../containers/{container['name']}",
                extra_options=["--platform", "linux/amd64"],
            ),
            # TODO: use more human readable names in ECR
            image_name=image_name,
            local_image_name=container["tag"],
            registry=registry_info,
        )

        # Export the base and specific version image name.
        pulumi.export(f"{container['name']}-base-image-name", image.base_image_name)
        pulumi.export(f"{container['name']}-full-image-name", image.image_name)
