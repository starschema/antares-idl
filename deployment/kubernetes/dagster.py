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


def deploy_dagster(resources):

    if resources["components"]["postgresql"]:
        dagster_helm_values = {
            "postgresql": {
                "enabled": False,
                "postgresqlUsername": resources["postgresql"].values["auth"][
                    "username"
                ],
                "postgresqlPassword": resources["postgresql"].values["auth"][
                    "password"
                ],
                "postgresqlDatabase": resources["postgresql"].values["auth"][
                    "database"
                ],
                "postgresqlHost": "postgresql",
            },
        }
    else:
        dagster_helm_values = {}

    # TODO: Add dependency in case of postgres-repository is used
    dagster_release = Release(
        "dagster",
        ReleaseArgs(
            chart="dagster",
            name="dagster",
            repository_opts=RepositoryOptsArgs(
                repo="https://dagster-io.github.io/helm",
            ),
            namespace=resources["namespace"].metadata["name"],
            values=dagster_helm_values,
        ),
    )

    resources["dagster"] = dagster_release

    return resources
