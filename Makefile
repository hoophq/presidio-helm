VERSION ?= $(or ${GIT_TAG},${GIT_TAG},v0)
GITCOMMIT ?= $(shell git rev-parse HEAD)
DIST_FOLDER ?= ./dist

test:
	helm lint chart/

release:
	mkdir -p ${DIST_FOLDER}
	helm package chart/ --app-version ${VERSION} --destination ${DIST_FOLDER}/ --version ${VERSION}
	helm registry login ghcr.io --username ${GITHUB_USERNAME} --password ${GITHUB_CONTAINER_REGISTRY_TOKEN}
	helm push ${DIST_FOLDER}/presidio-chart-${VERSION}.tgz oci://ghcr.io/hoophq/helm-charts/

publish:
	./scripts/publish-release.sh

.PHONY: test release publish
