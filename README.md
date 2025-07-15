# Presidio Helm Chart

A Presidio Helm Chart maintained by the Hoop team.

## Usage

To install a specific version, use the attribute `imageVersion`.

```sh
helm upgrade --install presidio \
	oci://ghcr.io/hoophq/helm-charts/presidio-chart --version v0.0.3 \
	--set imageVersion=2.2.358
```

See the release pages of Presidio for version information:
- https://github.com/microsoft/presidio/releases

### Available Values

Check the file [chart/values.yaml](./chart/values.yaml) that will contain all available values.
