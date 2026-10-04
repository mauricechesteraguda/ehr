# type-10042026-Maurice: platform targets deliberately avoid cloud credentials.
.PHONY: platform-helm-lint platform-render-k3s platform-test-ticket05 kind-e2e

platform-helm-lint:
	helm dependency build platform/helm/ehr
	helm lint platform/helm/ehr

platform-render-k3s:
	helm dependency build platform/helm/ehr
	helm template ehr platform/helm/ehr -f platform/helm/ehr/values-k3s.yaml --set image.repository=example.invalid/ehr --set image.webRepository=example.invalid/ehr-web

platform-test-ticket05:
	python3 -m pytest -q backend/tests/test_ticket05_platform.py --maxfail=1

kind-e2e:
	EHR_KIND_E2E=1 python3 -m pytest -q backend/tests/test_ticket05_platform.py -k kind --maxfail=1
