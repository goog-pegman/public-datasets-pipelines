# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest
from ruamel import yaml

from scripts import generate_terraform

PROJECT_ROOT = generate_terraform.PROJECT_ROOT
SAMPLE_YAML_PATHS = {
    "dataset": PROJECT_ROOT / "samples" / "dataset.yaml",
    "pipeline": PROJECT_ROOT / "samples" / "pipeline.yaml",
}

ENV_PATH = PROJECT_ROOT / ".test"
ENV_DATASETS_PATH = ENV_PATH / "datasets"

yaml = yaml.YAML(typ="safe")


@pytest.fixture
def dataset_path():
    with tempfile.TemporaryDirectory(
        dir=generate_terraform.DATASETS_PATH, suffix="_dataset"
    ) as dir_path:
        yield pathlib.Path(dir_path)


@pytest.fixture
def pipeline_path(dataset_path, suffix="_pipeline"):
    with tempfile.TemporaryDirectory(dir=dataset_path, suffix=suffix) as dir_path:
        yield pathlib.Path(dir_path)


@pytest.fixture
def project_id() -> str:
    return "test-gcp-project-id"


@pytest.fixture
def bucket_name_prefix() -> str:
    return "1234-zyxwvu"


@pytest.fixture
def region() -> str:
    return "us-east4"


@pytest.fixture
def impersonating_acct() -> str:
    return "test-impersonator@project.iam.gserviceaccount.com"


@pytest.fixture
def gcs_bucket_resource() -> dict:
    return {
        "type": "storage_bucket",
        "name": "{{ friendly_project_id }}.{{ dataset_id }}",
    }


@pytest.fixture
def bq_table_resource() -> dict:
    return {
        "type": "bigquery_table",
        "table_id": "test_bq_table",
        "schema": [
            {"name": "test_col_string", "type": "STRING"},
            {"name": "test_col_int", "type": "INT64"},
            {"name": "test_col_numeric", "type": "NUMERIC"},
            {"name": "test_col_datetime", "type": "DATETIME"},
            {"name": "test_col_struct", "type": "STRUCT"},
        ],
    }


@pytest.fixture
def tf_state_bucket() -> str:
    return "test-terraform-state-bucket"


@pytest.fixture
def tf_state_prefix() -> str:
    return "test/terraform/state"


@pytest.fixture
def env() -> str:
    return "test"


def test_tf_templates_exist():
    for _, filepath in generate_terraform.TEMPLATE_PATHS.items():
        assert filepath.exists()


def test_main_generates_tf_files(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
    tf_state_bucket,
    tf_state_prefix,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        tf_state_bucket,
        tf_state_prefix,
    )

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        assert (path_prefix / "provider.tf").exists()
        assert (path_prefix / f"{dataset_path.name}_dataset.tf").exists()
        assert (path_prefix / f"{pipeline_path.name}_pipeline.tf").exists()
        assert (path_prefix / "variables.tf").exists()

    assert not (
        generate_terraform.DATASETS_PATH
        / dataset_path.name
        / "_terraform"
        / "terraform.tfvars"
    ).exists()

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "terraform.tfvars"
    ).exists()

    assert not (
        generate_terraform.DATASETS_PATH
        / dataset_path.name
        / "_terraform"
        / "backend.tf"
    ).exists()

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "backend.tf"
    ).exists()


def test_main_without_tf_remote_state_generates_tf_files_except_backend_tf(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        None,
        None,
    )

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        assert (path_prefix / "provider.tf").exists()
        assert (path_prefix / f"{dataset_path.name}_dataset.tf").exists()
        assert (path_prefix / f"{pipeline_path.name}_pipeline.tf").exists()
        assert (path_prefix / "variables.tf").exists()
        assert not (path_prefix / "backend.tf").exists()

    assert not (
        generate_terraform.DATASETS_PATH
        / dataset_path.name
        / "_terraform"
        / "terraform.tfvars"
    ).exists()

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "terraform.tfvars"
    ).exists()


pipeline_path_2 = pipeline_path


def test_main_with_multiple_pipelines(
    dataset_path,
    pipeline_path,
    pipeline_path_2,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
    tf_state_bucket,
    tf_state_prefix,
):
    assert pipeline_path.name != pipeline_path_2.name

    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path_2 / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        tf_state_bucket,
        tf_state_prefix,
    )

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        assert (path_prefix / "provider.tf").exists()
        assert (path_prefix / f"{dataset_path.name}_dataset.tf").exists()
        assert (path_prefix / f"{pipeline_path.name}_pipeline.tf").exists()
        assert (path_prefix / f"{pipeline_path_2.name}_pipeline.tf").exists()
        assert (path_prefix / "variables.tf").exists()

    assert not (
        generate_terraform.DATASETS_PATH
        / dataset_path.name
        / "_terraform"
        / "terraform.tfvars"
    ).exists()

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "terraform.tfvars"
    ).exists()

    assert not (
        generate_terraform.DATASETS_PATH
        / dataset_path.name
        / "_terraform"
        / "backend.tf"
    ).exists()

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "backend.tf"
    ).exists()


def test_dataset_without_any_pipelines(
    dataset_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
    tf_state_bucket,
    tf_state_prefix,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        tf_state_bucket,
        tf_state_prefix,
    )

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        assert (path_prefix / "provider.tf").exists()
        assert (path_prefix / f"{dataset_path.name}_dataset.tf").exists()

    assert not (
        generate_terraform.DATASETS_PATH
        / dataset_path.name
        / "_terraform"
        / "terraform.tfvars"
    ).exists()

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "terraform.tfvars"
    ).exists()

    assert not (
        generate_terraform.DATASETS_PATH
        / dataset_path.name
        / "_terraform"
        / "backend.tf"
    ).exists()

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "backend.tf"
    ).exists()


def test_dataset_path_does_not_exist(
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
    tf_state_bucket,
    tf_state_prefix,
):
    with pytest.raises(FileNotFoundError):
        generate_terraform.main(
            "non_existing_dir",
            project_id,
            bucket_name_prefix,
            region,
            impersonating_acct,
            env,
            tf_state_bucket,
            tf_state_prefix,
        )


def test_generated_tf_files_contain_license_headers(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
    tf_state_bucket,
    tf_state_prefix,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        tf_state_bucket,
        tf_state_prefix,
    )

    license_header = pathlib.Path(
        generate_terraform.TEMPLATE_PATHS["license"]
    ).read_text()

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        assert (path_prefix / "provider.tf").read_text().count(license_header) == 1
        assert (path_prefix / f"{dataset_path.name}_dataset.tf").read_text().count(
            license_header
        ) == 1
        assert (path_prefix / f"{pipeline_path.name}_pipeline.tf").read_text().count(
            license_header
        ) == 1
        assert (path_prefix / "variables.tf").read_text().count(license_header) == 1

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "terraform.tfvars"
    ).read_text().count(license_header) == 1

    assert (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform" / "backend.tf"
    ).read_text().count(license_header) == 1


def test_dataset_tf_file_contains_description_when_specified(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        None,
        None,
    )

    config = yaml.load(open(dataset_path / "dataset.yaml"))
    bq_dataset = next(
        (r for r in config["resources"] if r["type"] == "bigquery_dataset"), None
    )
    assert bq_dataset
    assert bq_dataset["description"]

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        assert (path_prefix / f"{dataset_path.name}_dataset.tf").read_text().count(
            f"description = \"{bq_dataset['description']}\""
        ) == 1


def test_dataset_tf_has_no_bq_dataset_description_when_unspecified(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    config = yaml.load(open(dataset_path / "dataset.yaml"))

    # Get the first bigquery_dataset resource and delete the `description` field
    bq_dataset = next(
        (r for r in config["resources"] if r["type"] == "bigquery_dataset")
    )
    del bq_dataset["description"]
    with open(dataset_path / "dataset.yaml", "w") as file:
        yaml.dump(config, file)

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        None,
        None,
    )

    # Match the "google_bigquery_dataset" properties, i.e. any lines between the
    # curly braces, in the *_dataset.tf file
    regexp = r"\"google_bigquery_dataset\" \"" + dataset_path.name + r"\" \{(.*?)\}"
    bq_dataset_tf_string = re.compile(regexp, flags=re.MULTILINE | re.DOTALL)

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        result = bq_dataset_tf_string.search(
            (path_prefix / f"{dataset_path.name}_dataset.tf").read_text()
        )

        assert re.search(r"dataset_id\s+\=", result.group(1))
        assert not re.search(r"description\s+\=", result.group(1))


def test_pipeline_tf_contains_bq_table_description_when_specified(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        None,
        None,
    )

    config = yaml.load(open(pipeline_path / "pipeline.yaml"))
    bq_table = next(
        (r for r in config["resources"] if r["type"] == "bigquery_table"), None
    )
    assert bq_table
    assert bq_table["description"]

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        assert (path_prefix / f"{pipeline_path.name}_pipeline.tf").read_text().count(
            f"description = \"{bq_table['description']}\""
        ) == 1


def test_pipeline_tf_has_no_bq_table_description_when_unspecified(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    config = yaml.load(open(pipeline_path / "pipeline.yaml"))

    # Get the first bigquery_table resource and delete the `description` field
    bq_table = next(
        (r for r in config["resources"] if r["type"] == "bigquery_table"), None
    )
    del bq_table["description"]
    with open(pipeline_path / "pipeline.yaml", "w") as file:
        yaml.dump(config, file)

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        None,
        None,
    )

    # Match the "google_bigquery_table" properties, i.e. any lines between the
    # curly braces, in the *_pipeline.tf file
    regexp = r"\"google_bigquery_table\" \"" + bq_table["table_id"] + r"\" \{(.*?)\}"
    bq_table_tf_string = re.compile(regexp, flags=re.MULTILINE | re.DOTALL)

    for path_prefix in (
        ENV_DATASETS_PATH / dataset_path.name / "_terraform",
        generate_terraform.DATASETS_PATH / dataset_path.name / "_terraform",
    ):
        result = bq_table_tf_string.search(
            (path_prefix / f"{pipeline_path.name}_pipeline.tf").read_text()
        )

        assert re.search(r"table_id\s+\=", result.group(1))
        assert not re.search(r"description\s+\=", result.group(1))


def test_bucket_names_must_not_contain_dots_and_google():
    for name in (
        "test.bucket.name",
        "google-bucket",
        "google.bucket.name",
        "g00gle",
        "googl3",
    ):
        with pytest.raises(ValueError):
            generate_terraform.validate_bucket_name(name)


def test_bucket_names_must_use_hyphens_instead_of_underscores():
    for name in (
        "test_underscore",
        "test-bucket_with-underscore",
    ):
        with pytest.raises(ValueError):
            generate_terraform.validate_bucket_name(name)


def test_bucket_prefixes_must_use_hyphens_instead_of_underscores(
    dataset_path,
    project_id,
    region,
    impersonating_acct,
    env,
    tf_state_bucket,
    tf_state_prefix,
):
    for prefix in (
        "test_prefix",
        "test-hyphens_and_underscores",
    ):
        with pytest.raises(ValueError):
            generate_terraform.main(
                dataset_path.name,
                project_id,
                prefix,
                region,
                impersonating_acct,
                env,
                tf_state_bucket,
                tf_state_prefix,
            )


def test_validation_on_generated_tf_files_in_dot_env_dir(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        None,
        None,
    )
    env_dataset_path = ENV_DATASETS_PATH / dataset_path.name

    subprocess.check_call(["terraform", "init"], cwd=env_dataset_path / "_terraform")
    subprocess.check_call(
        ["terraform", "validate"], cwd=env_dataset_path / "_terraform"
    )


def test_validation_on_generated_tf_files_in_project_dir(
    dataset_path,
    pipeline_path,
    project_id,
    bucket_name_prefix,
    region,
    impersonating_acct,
    env,
):
    shutil.copyfile(SAMPLE_YAML_PATHS["dataset"], dataset_path / "dataset.yaml")
    shutil.copyfile(SAMPLE_YAML_PATHS["pipeline"], pipeline_path / "pipeline.yaml")

    generate_terraform.main(
        dataset_path.name,
        project_id,
        bucket_name_prefix,
        region,
        impersonating_acct,
        env,
        None,
        None,
    )
    project_dataset_path = generate_terraform.DATASETS_PATH / dataset_path.name

    subprocess.check_call(
        ["terraform", "init"], cwd=(project_dataset_path / "_terraform")
    )
    subprocess.check_call(
        ["terraform", "validate"], cwd=(project_dataset_path / "_terraform")
    )
