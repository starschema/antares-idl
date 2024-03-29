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

from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
import pulumi_random as random
from antares_common.resources import resources, enabled_components
from antares_common.config import config


def deploy():
    password = random.RandomPassword(
        "password", length=16, special=True, override_special="_%@"
    )

    if config["components"]["efs-eks"][:]:
        storage_class = resources["efs-sc-user-1001"].metadata["name"]
    else:
        # TODO: check without storage class
        storage_class = config.get("/postgresql/storage-class", "")

    postgresql_release = Release(
        "postgresql",
        ReleaseArgs(
            chart="postgresql",
            name="postgresql",
            repository_opts=RepositoryOptsArgs(
                repo="https://charts.bitnami.com/bitnami",
            ),
            namespace=resources["namespace"].metadata["name"],
            values={
                "auth": {
                    "username": "antares",
                    "password": password.result,
                    "database": "antares",
                },
                "primary": {
                    "initdb": {
                        "scripts": dict(
                            [
                                (
                                    f"init-{c}.sql",
                                    f'CREATE DATABASE "{c}" WITH OWNER antares;',
                                )
                                for c in enabled_components() - {"postgresql"}
                            ]
                        )
                    }
                },
                "global": ({"storageClass": storage_class} if storage_class else {}),
                **(config.get("/postgresql/helm-values", {})),
            },
        ),
    )

    resources["postgresql"] = postgresql_release

    return
