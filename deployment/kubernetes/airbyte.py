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


def deploy_airbyte(resources):

    # TODO: check if external or internal postgres is used.
    if resources["components"]["postgresql"]:
        airbyte_helm_values = {
            "global": {
                "database": {
                    "secretName": "postgresql",
                    "secretValue": "password",
                    "host": "postgresql",
                }
            },
            "postgresql": {"enabled": False},
            "externalDatabase": {
                "host": "postgresql",
                "user": resources["postgresql"].values["auth"]["username"],
                "existingSecret": "postgresql",
                "existingSecretPasswordKey": "password",
                "database": resources["postgresql"].values["auth"]["database"],
            },
        }
    else:
        airbyte_helm_values = {}

    # TODO: Add dependency in case of postgres-repository is used
    airbyte_release = Release(
        "airbyte",
        ReleaseArgs(
            chart="airbyte",
            name="airbyte",
            repository_opts=RepositoryOptsArgs(
                repo="https://airbytehq.github.io/helm-charts",
            ),
            namespace=resources["namespace"].metadata["name"],
            values=airbyte_helm_values,
        ),
    )

    resources["airbyte"] = airbyte_release

    return resources
