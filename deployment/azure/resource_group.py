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
from pulumi import Config as PulumiConfig
from pulumi_azure_native import (
    resources as azresources,
    network,
)

from antares_common.resources import resources
from antares_common.config import config


def deploy():
    prefix = f"antares-{config.stack}"
    azure_native_config = PulumiConfig("azure-native")

    resource_group = azresources.ResourceGroup(
        f"{prefix}-rg",
        location=config.get("location", azure_native_config.require("location")),
    )

    resources["resource-group"] = resource_group
    pulumi.export("resource-group-name", resource_group.name)

    vnet = network.VirtualNetwork(
        f"{prefix}-vnet",
        location=resource_group.location,
        resource_group_name=resource_group.name,
        address_space={
            "address_prefixes": ["10.0.0.0/16"],
        },
    )

    subnet = network.Subnet(
        f"{prefix}-subnet",
        resource_group_name=resource_group.name,
        address_prefix="10.0.0.0/24",
        virtual_network_name=vnet.name,
    )

    resources["vnet"] = vnet
    resources["subnet"] = subnet
