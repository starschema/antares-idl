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
import os
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
    acr_name = config.get(
        "/acr/registry-name", f"antares{config.org}{config.stack}".replace("-", "")
    )

    acr_registry = containerregistry.Registry(
        "antares-acr",
        admin_user_enabled=True,
        location=config.get(
            "/acr/location", pulumi.Config("azure-native").require("location")
        ),
        # registry name can only contain alphanumeric characters and no hyphens
        registry_name=acr_name,
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

    registry_info = docker.RegistryArgs(
        server=acr_registry.login_server,
        username=creds.username,
        password=creds.password,
    )

    # Publish all the images to the registry.
    for container in os.listdir("../../containers"):
        print("container: ", container)
        image_name = f"{acr_name}.azurecr.io/{container}:latest"
        print(image_name)

        image = docker.Image(
            f"{container}-docker-image",
            build=docker.DockerBuildArgs(
                context=f"../../containers/{container}",
                args={"--platform": "linux/amd64"},
                platform="linux/amd64",
            ),
            image_name=image_name,
            registry=registry_info,
            opts=pulumi.ResourceOptions(depends_on=[acr_registry]),
        )

        # Export the base and specific version image name.
        pulumi.export(f"{container}-base-image-name", image.base_image_name)
        pulumi.export(f"{container}-full-image-name", image.image_name)
