# Antares iDL - Modern Data Stack as Code

Welcome to the Antares iDL project! This repository is an infrastructure as code solution for deploying modern data stack components to the cloud (Amazon or Azure) or Kubernetes.

## Features

- Deployment scripts written in Pulumi and Python
- Support for popular projects such as dbt, Airbyte, Fivetran, Dagster, Airflow, Redata, Snowflake, Databricks, Tableau, OpenMetadata, and OpenLineage
- Data governance with preloaded dashboards for a single pane of glass view
- Strong and transparent security measures
- Data quality, lineage, and audit features

## Getting Started

To get started with Antares iDL, you will need to have Pulumi and Python installed on your system. 

1. Clone the repository to your local machine:

```
git clone https://github.com/starschema/antares-idl.git
```

2. Navigate to the directory:

```
cd antares-idl
```

3. Set up your cloud provider credentials as described in the [Pulumi documentation](https://www.pulumi.com/docs/intro/cloud-providers/index/).

4. Choose the components you want to deploy from the list of supported projects in the Features section above, and modify the deployment script as needed. The scripts are in `deployment/[component]` folders.

5. Run the deployment script:

```
pulumi up
```


## Contributing

We welcome contributions to the Antares iDL project! If you have an idea for a new feature or have found a bug, please open an issue on the repository. If you would like to submit a pull request, please follow these guidelines:

1. Fork the repository and create a new branch for your feature or bug fix.
2. Make your changes, including appropriate test cases.
3. Ensure that the test suite passes by running `pulumi test`.
4. Add your name to the CONTRIBUTORS file.
5. Submit a pull request.

## License

Antares iDL is licensed under the [MIT License](LICENSE).

