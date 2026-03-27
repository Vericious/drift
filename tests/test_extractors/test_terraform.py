"""Tests for terraform module."""

from pathlib import Path

import pytest

from drift.extractors.terraform import TerraformExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_terraform.tf"


class TestTerraformExtractor:
    """Test TerraformExtractor."""

    def test_can_handle_tf_file(self):
        """.can_handle returns True for .tf files."""
        extractor = TerraformExtractor()
        assert extractor.can_handle(Path("foo.tf")) is True
        assert extractor.can_handle(Path("foo.tf.json")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_resource_facts(self):
        """Extracts resource facts from the fixture."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        resource_facts = [f for f in facts if f.metadata.get("is_resource")]
        assert len(resource_facts) > 0

    def test_kind_is_config_key(self):
        """All extracted facts have kind=config_key."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "config_key" for f in facts)

    def test_resource_types_extracted(self):
        """Resource types are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        resource_facts = [f for f in facts if f.metadata.get("is_resource")]
        types = {f.metadata.get("resource_type") for f in resource_facts}
        assert "aws_s3_bucket" in types
        assert "aws_instance" in types
        assert "aws_vpc" in types

    def test_resource_names_extracted(self):
        """Resource names are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        resource_facts = [f for f in facts if f.metadata.get("is_resource")]
        names = {f.metadata.get("resource_name") for f in resource_facts}
        assert "app_bucket" in names
        assert "web_server" in names
        assert "main" in names

    def test_fact_name_format_resource_type_resource_name(self):
        """Fact names follow 'resource_type.resource_name' format for resources."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        resource_facts = [f for f in facts if f.metadata.get("is_resource")]
        names = {f.name for f in resource_facts}
        assert "aws_s3_bucket.app_bucket" in names
        assert "aws_instance.web_server" in names
        assert "aws_vpc.main" in names

    def test_extracts_variable_facts(self):
        """Variable facts are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        var_facts = [f for f in facts if f.metadata.get("is_variable")]
        assert len(var_facts) > 0

    def test_variable_names_extracted(self):
        """Variable names are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        var_facts = [f for f in facts if f.metadata.get("is_variable")]
        names = {f.metadata.get("variable_name") for f in var_facts}
        assert "region" in names
        assert "environment" in names
        assert "instance_type" in names

    def test_fact_name_format_var_variable_name(self):
        """Fact names follow 'var.variable_name' format for variables."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        var_facts = [f for f in facts if f.metadata.get("is_variable")]
        names = {f.name for f in var_facts}
        assert "var.region" in names
        assert "var.environment" in names
        assert "var.instance_type" in names

    def test_extracts_output_facts(self):
        """Output facts are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        output_facts = [f for f in facts if f.metadata.get("is_output")]
        assert len(output_facts) > 0

    def test_output_names_extracted(self):
        """Output names are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        output_facts = [f for f in facts if f.metadata.get("is_output")]
        names = {f.metadata.get("output_name") for f in output_facts}
        assert "bucket_name" in names
        assert "instance_ip" in names
        assert "vpc_id" in names

    def test_fact_name_format_output_output_name(self):
        """Fact names follow 'output.output_name' format for outputs."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        output_facts = [f for f in facts if f.metadata.get("is_output")]
        names = {f.name for f in output_facts}
        assert "output.bucket_name" in names
        assert "output.instance_ip" in names
        assert "output.vpc_id" in names

    def test_extracts_data_source_facts(self):
        """Data source facts are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        data_facts = [f for f in facts if f.metadata.get("is_data")]
        assert len(data_facts) > 0

    def test_multiple_resources_of_same_type(self):
        """Multiple resources of the same type are extracted."""
        extractor = TerraformExtractor()
        facts = extractor.extract(FIXTURE)
        s3_facts = [f for f in facts if f.metadata.get("resource_type") == "aws_s3_bucket"]
        assert len(s3_facts) >= 1
