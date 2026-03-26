# Presidio Helm Chart

A Presidio Helm Chart maintained by the Hoop team.

## Usage

To install a specific version, use the attribute `<component>.imageTag`.

```sh
helm upgrade --install presidio \
	oci://ghcr.io/hoophq/helm-charts/presidio-chart --version v0.1.0 \
	--set analyzer.imageTag=2.2.362 \
	--set anonymizer.imageTag=2.2.362
```

See the release pages of Presidio for version information:
- https://github.com/microsoft/presidio/releases

### Available Values

Check the file [chart/values.yaml](./chart/values.yaml) that will contain all available values.
