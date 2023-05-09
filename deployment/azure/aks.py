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
from pulumi_azure_native import (
    containerservice,
    authorization,
)
import pulumi_azuread as azuread

from antares_common.resources import resources
from antares_common.config import config


def deploy():
    prefix = f"antares-{config.stack}"
    subscription_id = authorization.get_client_config().subscription_id

    # # create random password for the service principal
    # password = random.RandomPassword(
    #     "aks-sp-password", length=16, special=True, override_special="_%@"
    # )

    # Create Azure AD Application for AKS
    app = azuread.Application(f"{prefix}-aks-app", display_name=f"{prefix}-aks-app")
    resources["aks-app"] = app

    # Create service principal for the application so AKS can act on behalf of the application
    sp = azuread.ServicePrincipal("aks-sp", application_id=app.application_id)
    resources["aks-sp"] = sp

    # Create the service principal password
    sppwd = azuread.ServicePrincipalPassword(
        "aks-sp-pwd",
        service_principal_id=sp.id,
        end_date="2099-01-01T00:00:00Z",
    )

    subnet_assignment = authorization.RoleAssignment(
        "aks-subnet-permissions",
        principal_id=sp.id,
        principal_type=authorization.PrincipalType.SERVICE_PRINCIPAL,
        role_definition_id=f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions/4d97b98b-1d4f-4787-a291-c67834d212e7",  # ID for Network Contributor role
        scope=resources["subnet"].id,
    )

    # Create the AKS cluster
    # TODO: use custom config for the cluster
    aks = containerservice.ManagedCluster(
        f"{prefix}-aks",
        location=resources["resource-group"].location,
        resource_group_name=resources["resource-group"].name,
        dns_prefix="dns",
        agent_pool_profiles=[
            {
                "name": "type1",
                "mode": "System",
                "count": 1,
                "vm_size": "Standard_B2ms",
                "os_type": containerservice.OSType.LINUX,
                "max_pods": 110,
                "vnet_subnet_id": resources["subnet"].id,
            }
        ],
        linux_profile={
            "admin_username": "azureuser",
            "ssh": {"public_keys": [{"key_data": config.get("/aks/ssh-key")}]},
        },
        service_principal_profile={
            "client_id": app.application_id,
            "secret": sppwd.value,
        },
        enable_rbac=True,
        network_profile={
            "network_plugin": "azure",
            "service_cidr": "10.10.0.0/16",
            "dns_service_ip": "10.10.0.10",
            "docker_bridge_cidr": "172.17.0.1/16",
        },
        auto_scaler_profile=containerservice.ManagedClusterPropertiesAutoScalerProfileArgs(
            scale_down_delay_after_add="5m",
            scan_interval="20s",
        ),
        opts=ResourceOptions(depends_on=[subnet_assignment]),
        **(config.get("/aks/cluster/managed-cluster-args", {})),
    )

    kube_creds = pulumi.Output.all(resources["resource-group"].name, aks.name).apply(
        lambda args: containerservice.list_managed_cluster_user_credentials(
            resource_group_name=args[0], resource_name=args[1]
        )
    )

    kube_config = kube_creds.kubeconfigs[0].value.apply(
        lambda enc: base64.b64decode(enc).decode()
    )

    resources["kube-config"] = kube_config
    resources["aks"] = aks

    # custom_provider = Provider("inflation_provider", kubeconfig=kube_config)

    pulumi.export("aks-name", aks.name)
