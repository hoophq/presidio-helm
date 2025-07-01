# Presidio Helm Chart

A Presidio Helm Chart maintained by the Hoop team.

## Usage

To install a specific version, use the value `imageVersion`.

```sh
helm upgrade --install presidio \
	oci://ghcr.io/hoophq/helm-charts/presidio-chart --version 0.0.1 \
	--set imageVersion=2.2.358
```

See the release pages for version information:
- https://github.com/microsoft/presidio/releases

### Available Values

Check the file [chart/values.yaml](./chart/values.yaml) that will contain all available values.

## Development

Use the command below to validate the templates

```sh
helm template chart/
```
