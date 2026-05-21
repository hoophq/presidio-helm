# presidio-analyzer (Hoop custom build)

Custom Microsoft Presidio analyzer image used by the [Hoop Helm chart][chart]
to detect PII entities that aren't part of upstream Presidio.

Currently registered:

- `BR_CPF` — Brazilian CPF (Cadastro de Pessoa Física), with mod-11 checksum
  validation, plus an explicit reject for the conventionally-invalid
  all-same-digit values.

The image is a thin overlay on top of `mcr.microsoft.com/presidio-analyzer`.
It only *adds* files; it never modifies anything shipped by the upstream
image, which means upstream releases can be tracked just by bumping the
base tag in the `Dockerfile`.

[chart]: https://hoop.dev/docs/setup/deployment/presidio

## Using the image

### With the Hoop Helm chart

Override the analyzer image in `values.yaml`:

```yaml
analyzer:
  imageRepository: docker.io/hoophq/presidio-analyzer
  imageTag: 0.1.0
```

That's the only change required — `command`, `gunicornConfigFile`,
`resources`, `autoscaling`, etc. all stay at the chart's defaults. The
extension is loaded at Python interpreter startup (see *How it works*
below), independent of how gunicorn is invoked.

### Standalone

```bash
docker run --rm -p 3000:3000 hoophq/presidio-analyzer:0.1.0

# BR_CPF should appear in /supportedentities
curl -s http://localhost:3000/supportedentities | tr ',' '\n' | grep BR_CPF

# Detection
curl -s -X POST http://localhost:3000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"Meu CPF é 111.444.777-35","language":"en"}'
```

## Directory layout

```
.
├── Makefile                    # build / test / release commands
├── README.md
├── Dockerfile                  # overlay on mcr.microsoft.com/presidio-analyzer
├── .dockerignore
├── conf/
│   └── br-cpf-overlay.yml      # YAML additions to the recognizer registry
├── extensions/
│   ├── presidio_extensions.pth # auto-loaded by site.py at Python startup
│   └── presidio_extensions/    # importable package
│       ├── __init__.py
│       └── br_cpf.py           # BrCpfRecognizer (PatternRecognizer subclass)
├── scripts/
│   ├── analyzer-test.sh        # ad-hoc /analyze CLI
│   └── e2e.sh                  # end-to-end smoke test driver
└── tests/
    ├── conftest.py
    └── test_br_cpf.py          # unit + integration tests
```

## How it works

Three pieces, all *additive* to the upstream image.

### 1. The recognizer class

`extensions/presidio_extensions/br_cpf.py` defines `BrCpfRecognizer`,
a `PatternRecognizer` subclass that:

- declares two patterns (formatted `XXX.XXX.XXX-XX` and bare `XXXXXXXXXXX`),
- carries Portuguese context words ("cpf", "cadastro", "pessoa física"…),
- overrides `validate_result` to enforce the mod-11 checksum and reject
  all-same-digit strings.

Presidio's `PatternRecognizer` clamps the score to `MAX_SCORE` (1.0) when
`validate_result` returns `True`, so a passing checksum produces a hard
1.0 confidence; a failing one drops the match entirely.

### 2. The `.pth` file (the auto-loading seam)

`extensions/presidio_extensions.pth` is installed into the interpreter's
site-packages at build time. Its three lines are:

```
/app
/app/extensions
import presidio_extensions
```

Python's `site.py` processes this file at every interpreter startup,
*before* any user code runs. The path lines put `/app` and
`/app/extensions` on `sys.path`; the import line then registers our
recognizer class into `EntityRecognizer.__subclasses__()`. By the time
Presidio's `AnalyzerEngineProvider` walks that set to resolve YAML
`class_name` entries, our class is already there.

This is the part that makes the image drop-in for the Hoop Helm chart:
the chart overrides the container `command` and sets its own
`GUNICORN_CMD_ARGS`, so anything we'd wire through gunicorn (a custom
config file, `entrypoint.sh`, the upstream `app.py`) gets replaced. But
`.pth` files run before gunicorn even parses its arguments, so the
registration happens regardless.

### 3. The YAML overlay

`conf/br-cpf-overlay.yml` lists only our additions:

```yaml
recognizers:
  - name: BrCpfRecognizer
    type: predefined
    country_code: br
    supported_languages:
      - language: en
        context: [cpf, documento, ...]
```

At build time the Dockerfile merges this with the upstream
`default_recognizers.yaml` into `/app/extensions/conf/recognizers.yml`,
then sets `ENV RECOGNIZER_REGISTRY_CONF_FILE` to point at the merged
file. The merge appends only entries whose `name` is new, so the
upstream defaults are preserved untouched. A future upstream release
that happens to add a recognizer with the same name will not produce a
duplicate.

## Development

### Prerequisites

- Docker with buildx (`docker buildx version`)
- Python 3.10+ (for local unit tests)
- `make`

For local tests:

```bash
pip install presidio-analyzer pytest
```

### Make targets

Run `make` for the full list. The most useful ones:

| Target              | Purpose                                                 |
|---------------------|---------------------------------------------------------|
| `make build`        | Build a single-arch image for local dev                 |
| `make buildx`       | Multi-arch build (amd64 + arm64), kept in buildx cache  |
| `make release`      | Multi-arch build *and* push to the registry             |
| `make test`         | Run unit tests via local pytest                         |
| `make test-image`   | Run unit tests inside the built image                   |
| `make run`          | Start the analyzer locally on `:3000` (foreground)      |
| `make run-detached` | Same but in the background; pairs with `make stop`      |
| `make smoke`        | Hit a running analyzer with a CPF                       |
| `make e2e`          | Build → start → smoke-test → tear down, one shot        |
| `make shell`        | Drop into bash inside the built image                   |
| `make clean`        | Remove image tags and the buildx builder                |

Variables (override on the command line):

| Variable          | Default                              | Purpose                                  |
|-------------------|--------------------------------------|------------------------------------------|
| `IMAGE`           | `hoophq/presidio-analyzer`           | Image repo                               |
| `VERSION`         | `git describe` output (or `dev`)     | Image tag                                |
| `PLATFORMS`       | `linux/amd64,linux/arm64`            | Multi-arch targets                       |
| `BUILDX_BUILDER`  | `presidio-builder`                   | Buildx builder name                      |
| `PORT`            | `3000`                               | Host port for `make run` / `make smoke`  |

Example: `make release VERSION=0.2.0`

### Local test cycle

```bash
make build       # fast single-arch
make test        # local pytest (~1s)
make test-image  # validates runtime layout inside the image (~slower)
make e2e         # full end-to-end against a running container
```

### Smoke testing manually

```bash
make run-detached
./scripts/analyzer-test.sh "Meu CPF é 111.444.777-35"
echo "another one: 39053344705" | ./scripts/analyzer-test.sh
ENTITIES=BR_CPF ./scripts/analyzer-test.sh "CPF 111.444.777-35 email foo@bar.com"
make stop
```

See the script header for all environment knobs (`ANALYZER_URL`,
`LANGUAGE`, `SCORE_THRESHOLD`, `ENTITIES`).

## Adding a new recognizer

To add, say, a CNPJ recognizer (Brazilian company tax ID):

1. **Write the class** at `extensions/presidio_extensions/br_cnpj.py`,
   following `br_cpf.py` as the template. Set `COUNTRY_CODE = "br"`,
   declare patterns and context, and implement the CNPJ mod-11 in
   `validate_result`.

2. **Re-export from the package** so the `.pth` import picks it up:

   ```python
   # extensions/presidio_extensions/__init__.py
   from .br_cpf  import BrCpfRecognizer
   from .br_cnpj import BrCnpjRecognizer

   __all__ = ["BrCpfRecognizer", "BrCnpjRecognizer"]
   ```

3. **Add to the YAML overlay** (`conf/br-cpf-overlay.yml` — rename to
   `br-overlay.yml` if you're growing past CPF):

   ```yaml
   recognizers:
     - name: BrCpfRecognizer
       # …
     - name: BrCnpjRecognizer
       type: predefined
       country_code: br
       supported_languages:
         - language: en
           context: [cnpj, empresa, "cadastro nacional"]
   ```

4. **Write tests** at `tests/test_br_cnpj.py`, mirroring the shape of
   `test_br_cpf.py`: valid/invalid checksums, malformed input,
   integration via `analyze()`, metadata.

5. **Verify and release**:

   ```bash
   make test test-image e2e
   git commit -am "add BR_CNPJ recognizer"
   git tag 0.2.0
   make release
   ```

## Release process

1. Make sure tests pass:
   ```bash
   make test test-image
   ```
2. Tag the release:
   ```bash
   git tag 0.2.0
   git push --tags
   ```
3. Multi-arch build and push:
   ```bash
   make release
   ```
4. Bump `analyzer.imageTag` in the Helm chart values.

The `release` target refuses to publish if `VERSION` resolves to `dev`
or to a `dirty` git description. Override `VERSION` explicitly if you
need to ship an out-of-band build (e.g. `make release VERSION=0.1.1-rc1`).

## Troubleshooting

### `Invalid recognizer registry configuration` on startup

Presidio couldn't resolve a `class_name` entry in the YAML. Almost
always means the `.pth` file didn't run, so the recognizer class isn't
in `EntityRecognizer.__subclasses__()`. Verify:

```bash
docker run --rm --entrypoint /bin/sh hoophq/presidio-analyzer:<tag> -c \
  'python -c "import presidio_extensions; print(presidio_extensions.__file__)"'
```

If that prints a path under `/app/extensions/presidio_extensions/`, the
package is importable. If it errors, the `.pth` install in the
Dockerfile didn't land in the right site-packages directory — check the
build log for the path that `sysconfig.get_paths()['purelib']` resolved
to during the `RUN python -c "...shutil.copy..."` step.

### `BR_CPF` doesn't appear in `/supportedentities`

The merged YAML didn't include the BR_CPF entry. Inspect it inside the
image:

```bash
docker run --rm --entrypoint cat hoophq/presidio-analyzer:<tag> \
  /app/extensions/conf/recognizers.yml | grep -A4 BrCpfRecognizer
```

If the entry is missing, the build-time merge step didn't pick it up.
The most likely causes: `conf/br-cpf-overlay.yml` was excluded from the
build context (check `.dockerignore`), or upstream renamed
`default_recognizers.yaml` between Presidio versions (check the path in
the Dockerfile's `RUN python <<'PY' ... PY` block).

### `tldextract` errors on first request

The base image's EMAIL_ADDRESS recognizer fetches the Public Suffix
List on first use. We pre-cache it at build time with
`RUN poetry run tldextract --update`. If your build environment has no
outbound network, that step will warn but not fail; first-request will
then try to fetch the list and may block. Either give the builder
network access, or accept that the email recognizer needs network on
first request. See
[microsoft/presidio#1205](https://github.com/microsoft/presidio/issues/1205).

### Workflow when bumping the upstream Presidio version

1. Update the `FROM` tag in `Dockerfile` to the new upstream release.
2. `make build` — the build will fail loudly if upstream moved the
   `default_recognizers.yaml` path or changed the YAML schema.
3. `make test-image` — runs our test suite inside the new image; catches
   regressions in `PatternRecognizer.analyze` behavior or score clamping.
4. `make e2e` — confirms /analyze still returns BR_CPF correctly.
5. Tag and release.
