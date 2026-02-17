"""Unit tests for observability configuration files.

Validates OTEL collector, Prometheus, alerting rules, and Grafana dashboard
configs are well-formed YAML/JSON with the expected structure.  No running
services are required.
"""

import json
import os

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "../..")

OTEL_CONFIG = os.path.join(_REPO_ROOT, "config/otel/otel-collector-config.yaml")
PROMETHEUS_CONFIG = os.path.join(_REPO_ROOT, "config/prometheus.yml")
ALERTING_RULES = os.path.join(_REPO_ROOT, "kubernetes/base/observability/prometheus/alerting-rules.yaml")
GRAFANA_DASHBOARDS = [
    os.path.join(
        _REPO_ROOT,
        "kubernetes/base/observability/grafana/dashboards/ai-gateway-overview.json",
    ),
    os.path.join(
        _REPO_ROOT,
        "kubernetes/base/observability/grafana/dashboards/finops-cost-tracking.json",
    ),
]


# ============================================================================
# OTEL Collector Config
# ============================================================================


class TestOtelCollectorConfig:
    def test_valid_yaml(self):
        """OTEL collector config should be valid, parseable YAML."""
        with open(OTEL_CONFIG) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_has_required_sections(self):
        """Config should contain receivers, processors, exporters, and service.pipelines."""
        with open(OTEL_CONFIG) as f:
            data = yaml.safe_load(f)

        for section in ("receivers", "processors", "exporters"):
            assert section in data, f"Missing top-level section: {section}"

        assert "service" in data, "Missing top-level section: service"
        assert "pipelines" in data["service"], "Missing service.pipelines section"

    def test_pipeline_references_are_valid(self):
        """Pipeline receivers/processors/exporters should reference defined components."""
        with open(OTEL_CONFIG) as f:
            data = yaml.safe_load(f)

        defined_receivers = set(data.get("receivers", {}).keys())
        defined_processors = set(data.get("processors", {}).keys())
        defined_exporters = set(data.get("exporters", {}).keys())

        pipelines = data["service"]["pipelines"]
        for pipeline_name, pipeline_cfg in pipelines.items():
            for receiver in pipeline_cfg.get("receivers", []):
                assert receiver in defined_receivers, (
                    f"Pipeline '{pipeline_name}' references undefined receiver '{receiver}'"
                )
            for processor in pipeline_cfg.get("processors", []):
                assert processor in defined_processors, (
                    f"Pipeline '{pipeline_name}' references undefined processor '{processor}'"
                )
            for exporter in pipeline_cfg.get("exporters", []):
                assert exporter in defined_exporters, (
                    f"Pipeline '{pipeline_name}' references undefined exporter '{exporter}'"
                )


# ============================================================================
# Prometheus Config
# ============================================================================


class TestPrometheusConfig:
    def test_valid_yaml(self):
        """Prometheus config should be valid YAML."""
        with open(PROMETHEUS_CONFIG) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_scrape_configs_structure(self):
        """Each scrape config should have job_name and targets, with unique job names."""
        with open(PROMETHEUS_CONFIG) as f:
            data = yaml.safe_load(f)

        scrape_configs = data.get("scrape_configs")
        assert scrape_configs, "scrape_configs must be present and non-empty"

        job_names = []
        for idx, sc in enumerate(scrape_configs):
            assert "job_name" in sc, f"scrape_configs[{idx}] missing job_name"
            job_names.append(sc["job_name"])

            # targets live inside static_configs
            static_configs = sc.get("static_configs", [])
            assert static_configs, f"scrape_configs[{idx}] (job={sc['job_name']}) missing static_configs"
            for sc_idx, static in enumerate(static_configs):
                assert "targets" in static, f"scrape_configs[{idx}].static_configs[{sc_idx}] missing targets"

        assert len(job_names) == len(set(job_names)), f"Duplicate job_names found: {job_names}"


# ============================================================================
# Alerting Rules
# ============================================================================


class TestAlertingRules:
    def test_valid_yaml(self):
        """Alerting rules file should be valid YAML."""
        with open(ALERTING_RULES) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)

    def test_groups_have_complete_rules(self):
        """Each rule must have alert, expr, labels, and annotations."""
        with open(ALERTING_RULES) as f:
            data = yaml.safe_load(f)

        groups = data.get("spec", {}).get("groups", data.get("groups", []))
        assert groups, "No alert groups found"

        for group in groups:
            group_name = group.get("name", "<unnamed>")
            rules = group.get("rules", [])
            assert rules, f"Group '{group_name}' has no rules"

            for idx, rule in enumerate(rules):
                for field in ("alert", "expr", "labels", "annotations"):
                    assert field in rule, f"Group '{group_name}' rule[{idx}] missing '{field}'"

    def test_no_duplicate_alert_names(self):
        """Alert names should be unique across all groups."""
        with open(ALERTING_RULES) as f:
            data = yaml.safe_load(f)

        groups = data.get("spec", {}).get("groups", data.get("groups", []))
        alert_names = []
        for group in groups:
            for rule in group.get("rules", []):
                alert_names.append(rule["alert"])

        assert len(alert_names) == len(set(alert_names)), (
            f"Duplicate alert names: {[n for n in alert_names if alert_names.count(n) > 1]}"
        )


# ============================================================================
# Grafana Dashboards
# ============================================================================


class TestGrafanaDashboards:
    def test_valid_json(self):
        """Each Grafana dashboard file should be valid JSON."""
        for path in GRAFANA_DASHBOARDS:
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, dict), f"{os.path.basename(path)} is not a JSON object"

    def test_panels_have_type_and_title(self):
        """Every panel in each dashboard should have a type and title."""
        for path in GRAFANA_DASHBOARDS:
            with open(path) as f:
                data = json.load(f)

            panels = data.get("panels")
            dashboard_name = os.path.basename(path)
            assert panels, f"{dashboard_name} has no panels"

            for idx, panel in enumerate(panels):
                assert "type" in panel, f"{dashboard_name} panel[{idx}] missing 'type'"
                assert "title" in panel, f"{dashboard_name} panel[{idx}] missing 'title'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
