import json
import logging
import mock
import pytest
import requests_mock
import requests

from pubtools._quay import exceptions
from pubtools._quay import quay_client
from pubtools._quay import push_docker
from .utils.misc import sort_dictionary_sortable_values, compare_logs

# flake8: noqa: E501


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_init_verify_target_settings_ok(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    operator_push_item_ok,
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, operator_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    assert push_docker_instance.push_items == [container_multiarch_push_item, operator_push_item_ok]
    assert push_docker_instance.hub == hub
    assert push_docker_instance.task_id == "1"
    assert push_docker_instance.target_name == "some-target"
    assert push_docker_instance.target_settings == target_settings
    assert push_docker_instance.quay_host == "quay.io"
    mock_quay_client.assert_not_called()
    mock_quay_api_client.assert_not_called()

    assert push_docker_instance.quay_client == mock_quay_client.return_value
    assert push_docker_instance.quay_api_client == mock_quay_api_client.return_value
    mock_quay_client.assert_called_once_with("quay-user", "quay-pass", "quay.io")
    mock_quay_api_client.assert_called_once_with("quay-token", "quay.io")


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_init_verify_target_settings_missing_item(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    operator_push_item_ok,
):
    hub = mock.MagicMock()
    target_settings.pop("quay_user", None)
    with pytest.raises(exceptions.InvalidTargetSettings, match="'quay_user' must be present.*"):
        push_docker_instance = push_docker.PushDocker(
            [container_multiarch_push_item, operator_push_item_ok],
            hub,
            "1",
            "some-target",
            target_settings,
        )


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_init_verify_target_settings_missing_docker_item(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    operator_push_item_ok,
):
    hub = mock.MagicMock()
    target_settings["docker_settings"].pop("umb_urls", None)
    with pytest.raises(exceptions.InvalidTargetSettings, match="'umb_urls' must be present.*"):
        push_docker_instance = push_docker.PushDocker(
            [container_multiarch_push_item, operator_push_item_ok],
            hub,
            "1",
            "some-target",
            target_settings,
        )


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_init_verify_target_settings_missing_overwrite_index(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    operator_push_item_ok,
):
    hub = mock.MagicMock()
    target_settings.pop("iib_overwrite_from_index", None)
    with pytest.raises(exceptions.InvalidTargetSettings, match="Either both or neither of.*"):
        push_docker_instance = push_docker.PushDocker(
            [container_multiarch_push_item, operator_push_item_ok],
            hub,
            "1",
            "some-target",
            target_settings,
        )


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_container_push_items_ok(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    operator_push_item_ok,
    container_source_push_item,
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, operator_push_item_ok, container_source_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    items = push_docker_instance.get_docker_push_items()
    assert items == [container_multiarch_push_item, container_source_push_item]


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_container_push_items_errors(
    mock_quay_api_client, mock_quay_client, target_settings, container_push_item_errors
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_errors], hub, "1", "some-target", target_settings
    )
    with pytest.raises(exceptions.BadPushItem, match=".*contains errors.*"):
        items = push_docker_instance.get_docker_push_items()


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_container_push_items_no_pull_data(
    mock_quay_api_client, mock_quay_client, target_settings, container_push_item_no_metadata
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_no_metadata], hub, "1", "some-target", target_settings
    )
    with pytest.raises(exceptions.BadPushItem, match=".*doesn't contain pull data.*"):
        items = push_docker_instance.get_docker_push_items()


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_operator_push_items_ok(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    operator_push_item_ok,
    operator_push_item_ok2,
    container_push_item_ok,
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [operator_push_item_ok, operator_push_item_ok2, container_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    items = push_docker_instance.get_operator_push_items()
    assert items == [operator_push_item_ok, operator_push_item_ok2]


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_operator_push_items_ok(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    operator_push_item_ok,
    operator_push_item_ok2,
    container_push_item_ok,
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [operator_push_item_ok, operator_push_item_ok2, container_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    items = push_docker_instance.get_operator_push_items()
    assert items == [operator_push_item_ok, operator_push_item_ok2]


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_operator_push_item_errors(
    mock_quay_api_client, mock_quay_client, target_settings, operator_push_item_errors
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [operator_push_item_errors], hub, "1", "some-target", target_settings
    )
    with pytest.raises(exceptions.BadPushItem, match=".*contains errors.*"):
        items = push_docker_instance.get_operator_push_items()


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_operator_push_item_no_op_type(
    mock_quay_api_client, mock_quay_client, target_settings, operator_push_item_no_op_type
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [operator_push_item_no_op_type], hub, "1", "some-target", target_settings
    )
    with pytest.raises(exceptions.BadPushItem, match=".*doesn't contain 'op_type'.*"):
        items = push_docker_instance.get_operator_push_items()


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_operator_push_item_op_appregistry(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    operator_push_item_ok2,
    operator_push_item_appregistry,
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [operator_push_item_ok2, operator_push_item_appregistry],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    items = push_docker_instance.get_operator_push_items()
    assert items == [operator_push_item_ok2]


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_operator_push_item_unknown_op_type(
    mock_quay_api_client, mock_quay_client, target_settings, operator_push_item_unknown_op_type
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [operator_push_item_unknown_op_type], hub, "1", "some-target", target_settings
    )
    with pytest.raises(exceptions.BadPushItem, match=".*has unknown op_type.*"):
        items = push_docker_instance.get_operator_push_items()


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_operator_push_item_no_ocp_versions(
    mock_quay_api_client, mock_quay_client, target_settings, operator_push_item_no_ocp
):
    hub = mock.MagicMock()
    push_docker_instance = push_docker.PushDocker(
        [operator_push_item_no_ocp], hub, "1", "some-target", target_settings
    )
    with pytest.raises(exceptions.BadPushItem, match=".*specify 'com.redhat.openshift.versions'.*"):
        items = push_docker_instance.get_operator_push_items()


@mock.patch("pubtools._quay.push_docker.run_entrypoint")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_get_repo_metadata(
    mock_quay_api_client,
    mock_quay_client,
    mock_run_entrypoint,
    target_settings,
    container_multiarch_push_item,
    operator_push_item_ok,
):
    hub = mock.MagicMock()
    mock_run_entrypoint.return_value = {"key": "value"}
    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, operator_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    res = push_docker_instance.get_repo_metadata("some_repo", target_settings)

    assert res == {"key": "value"}
    mock_run_entrypoint.assert_called_once_with(
        ("pubtools-pyxis", "console_scripts", "pubtools-pyxis-get-repo-metadata"),
        "pubtools-pyxis-get-repo-metadata",
        [
            "--pyxis-server",
            "pyxis-url.com",
            "--pyxis-krb-principal",
            "some-principal@REDHAT.COM",
            "--pyxis-krb-ktfile",
            "/etc/pub/some.keytab",
            "--repo-name",
            "some_repo",
        ],
        {},
    )


@mock.patch("pubtools._quay.push_docker.PushDocker.get_repo_metadata")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_check_repos_validity_success(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_repo_metadata,
    target_settings,
    container_push_item_correct_repos,
    container_signing_push_item,
    container_push_item_external_repos,
):
    mock_get_target_info = mock.MagicMock()
    mock_get_target_info.return_value = {"settings": {"quay_namespace": "stage_namespace"}}
    mock_worker = mock.MagicMock()
    mock_worker.get_target_info = mock_get_target_info
    hub = mock.MagicMock()
    hub.worker = mock_worker

    mock_get_repository_data = mock.MagicMock()
    mock_get_repository_data.side_effect = ["repo_data1", "repo_data2", "repo_data3"]
    mock_quay_api_client.get_repository_data = mock_get_repository_data

    mock_get_repo_metadata.side_effect = [
        {"release_categories": "value2"},
        {"release_categories": "value1"},
        {"release_categories": "value2"},
    ]
    target_settings["propagated_from"] = "target_stage_quay"
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_correct_repos, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    push_docker_instance.check_repos_validity(
        [
            container_push_item_external_repos,
            container_push_item_correct_repos,
            container_signing_push_item,
        ],
        hub,
        target_settings,
        mock_quay_api_client,
    )

    mock_get_target_info.assert_called_once_with("target_stage_quay")
    assert mock_get_repo_metadata.call_count == 3
    mock_get_repo_metadata.call_args_list[0] == mock.call("namespace/repo1")
    mock_get_repo_metadata.call_args_list[1] == mock.call("namespace/repo2")
    mock_get_repo_metadata.call_args_list[2] == mock.call("namespace/repo3")
    assert mock_get_repository_data.call_count == 3
    mock_get_repository_data.call_args_list[0] == mock.call("some-namespace/namespace----repo1")
    mock_get_repository_data.call_args_list[1] == mock.call("some-namespace/namespace----repo2")


@mock.patch("pubtools._quay.push_docker.PushDocker.get_repo_metadata")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_check_repos_validity_missing_repo(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_repo_metadata,
    target_settings,
    container_push_item_ok,
    container_signing_push_item,
):
    mock_get_target_info = mock.MagicMock()
    mock_get_target_info.return_value = {"settings": {"quay_namespace": "stage_namespace"}}
    mock_worker = mock.MagicMock()
    mock_worker.get_target_info = mock_get_target_info
    hub = mock.MagicMock()
    hub.worker = mock_worker

    response = mock.MagicMock()
    response.status_code = 404
    mock_get_repo_metadata.side_effect = [
        {"release_categories": "value1"},
        requests.exceptions.HTTPError("missing", response=response),
    ]
    target_settings["propagated_from"] = "target_stage_quay"
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_ok, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    with pytest.raises(exceptions.InvalidRepository, match=".*doesn't exist in Comet.*"):
        push_docker_instance.check_repos_validity(
            [container_push_item_ok, container_signing_push_item],
            hub,
            target_settings,
            mock_quay_api_client,
        )

    mock_get_target_info.assert_called_once_with("target_stage_quay")
    assert mock_get_repo_metadata.call_count == 2
    mock_get_repo_metadata.call_args_list[0] == mock.call("namespace/repo1")
    mock_get_repo_metadata.call_args_list[1] == mock.call("namespace/repo2")


@mock.patch("pubtools._quay.push_docker.PushDocker.get_repo_metadata")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_check_repos_validity_get_repo_server_error(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_repo_metadata,
    target_settings,
    container_push_item_ok,
    container_signing_push_item,
):
    mock_get_target_info = mock.MagicMock()
    mock_get_target_info.return_value = {"settings": {"quay_namespace": "stage_namespace"}}
    mock_worker = mock.MagicMock()
    mock_worker.get_target_info = mock_get_target_info
    hub = mock.MagicMock()
    hub.worker = mock_worker

    response = mock.MagicMock()
    response.status_code = 500
    mock_get_repo_metadata.side_effect = [
        {"release_categories": "value1"},
        requests.exceptions.HTTPError("server error", response=response),
    ]
    target_settings["propagated_from"] = "target_stage_quay"
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_ok, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    with pytest.raises(requests.exceptions.HTTPError, match=".*server error.*"):
        push_docker_instance.check_repos_validity(
            [container_push_item_ok, container_signing_push_item],
            hub,
            target_settings,
            mock_quay_api_client,
        )

    mock_get_target_info.assert_called_once_with("target_stage_quay")
    assert mock_get_repo_metadata.call_count == 2
    mock_get_repo_metadata.call_args_list[0] == mock.call("namespace/repo1")
    mock_get_repo_metadata.call_args_list[1] == mock.call("namespace/repo2")


@mock.patch("pubtools._quay.push_docker.PushDocker.get_repo_metadata")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_check_repos_validity_deprecated_repo(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_repo_metadata,
    target_settings,
    container_push_item_ok,
    container_signing_push_item,
):
    mock_get_target_info = mock.MagicMock()
    mock_get_target_info.return_value = {"settings": {"quay_namespace": "stage_namespace"}}
    mock_worker = mock.MagicMock()
    mock_worker.get_target_info = mock_get_target_info
    hub = mock.MagicMock()
    hub.worker = mock_worker

    mock_get_repo_metadata.side_effect = [
        {"release_categories": "value1"},
        {"release_categories": "Deprecated"},
    ]
    target_settings["propagated_from"] = "target_stage_quay"
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_ok, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    with pytest.raises(exceptions.InvalidRepository, match=".*is deprecated.*"):
        push_docker_instance.check_repos_validity(
            [container_push_item_ok, container_signing_push_item],
            hub,
            target_settings,
            mock_quay_api_client,
        )

    mock_get_target_info.assert_called_once_with("target_stage_quay")
    assert mock_get_repo_metadata.call_count == 2
    mock_get_repo_metadata.call_args_list[0] == mock.call("namespace/repo1")
    mock_get_repo_metadata.call_args_list[1] == mock.call("namespace/repo2")


@mock.patch("pubtools._quay.push_docker.PushDocker.get_repo_metadata")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_check_repos_validity_missing_stage_repo(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_repo_metadata,
    target_settings,
    container_push_item_ok,
    container_signing_push_item,
):
    mock_get_target_info = mock.MagicMock()
    mock_get_target_info.return_value = {"settings": {"quay_namespace": "stage_namespace"}}
    mock_worker = mock.MagicMock()
    mock_worker.get_target_info = mock_get_target_info
    hub = mock.MagicMock()
    hub.worker = mock_worker

    response = mock.MagicMock()
    response.status_code = 404
    mock_get_repository_data = mock.MagicMock()
    mock_get_repository_data.side_effect = [
        "repo_data1",
        requests.exceptions.HTTPError("missing", response=response),
    ]
    mock_quay_api_client.get_repository_data = mock_get_repository_data

    mock_get_repo_metadata.side_effect = [
        {"release_categories": "value1"},
        {"release_categories": "value2"},
    ]
    target_settings["propagated_from"] = "target_stage_quay"
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_ok, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    with pytest.raises(exceptions.InvalidRepository, match=".*doesn't exist on stage.*"):
        push_docker_instance.check_repos_validity(
            [container_push_item_ok, container_signing_push_item],
            hub,
            target_settings,
            mock_quay_api_client,
        )

    mock_get_target_info.assert_called_once_with("target_stage_quay")
    assert mock_get_repo_metadata.call_count == 2
    mock_get_repo_metadata.call_args_list[0] == mock.call("namespace/repo1")
    mock_get_repo_metadata.call_args_list[1] == mock.call("namespace/repo2")
    assert mock_get_repository_data.call_count == 2
    mock_get_repository_data.call_args_list[0] == mock.call("some-namespace/namespace----repo1")
    mock_get_repository_data.call_args_list[1] == mock.call("some-namespace/namespace----repo2")


@mock.patch("pubtools._quay.push_docker.PushDocker.get_repo_metadata")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_check_repos_validity_get_stage_repo_server_error(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_repo_metadata,
    target_settings,
    container_push_item_ok,
    container_signing_push_item,
):
    mock_get_target_info = mock.MagicMock()
    mock_get_target_info.return_value = {"settings": {"quay_namespace": "stage_namespace"}}
    mock_worker = mock.MagicMock()
    mock_worker.get_target_info = mock_get_target_info
    hub = mock.MagicMock()
    hub.worker = mock_worker

    response = mock.MagicMock()
    response.status_code = 500
    mock_get_repository_data = mock.MagicMock()
    mock_get_repository_data.side_effect = [
        "repo_data1",
        requests.exceptions.HTTPError("server error", response=response),
    ]
    mock_quay_api_client.get_repository_data = mock_get_repository_data

    mock_get_repo_metadata.side_effect = [
        {"release_categories": "value1"},
        {"release_categories": "value2"},
    ]
    target_settings["propagated_from"] = "target_stage_quay"
    push_docker_instance = push_docker.PushDocker(
        [container_push_item_ok, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    with pytest.raises(requests.exceptions.HTTPError, match=".*server error*"):
        push_docker_instance.check_repos_validity(
            [container_push_item_ok, container_signing_push_item],
            hub,
            target_settings,
            mock_quay_api_client,
        )

    mock_get_target_info.assert_called_once_with("target_stage_quay")
    assert mock_get_repo_metadata.call_count == 2
    mock_get_repo_metadata.call_args_list[0] == mock.call("namespace/repo1")
    mock_get_repo_metadata.call_args_list[1] == mock.call("namespace/repo2")
    assert mock_get_repository_data.call_count == 2
    mock_get_repository_data.call_args_list[0] == mock.call("some-namespace/namespace----repo1")
    mock_get_repository_data.call_args_list[1] == mock.call("some-namespace/namespace----repo2")


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_generate_backup_mapping(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    container_signing_push_item,
):
    hub = mock.MagicMock()

    response = mock.MagicMock()
    response.status_code = 404
    mock_get_repository_data = mock.MagicMock()
    mock_get_repository_data.side_effect = [
        {"tags": {"latest-test-tag": {"manifest_digest": "sha256:a1a1a1a1a1a1"}}},
        requests.exceptions.HTTPError("missing", response=response),
        {"tags": {"some-other-tag": {"manifest_digest": "sha256:b2b2b2b2b2b2"}}},
    ]
    mock_quay_api_client.return_value.get_repository_data = mock_get_repository_data

    mock_get_manifest = mock.MagicMock()
    mock_get_manifest.return_value = "some-manifest-list"
    mock_quay_client.return_value.get_manifest = mock_get_manifest

    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    backup_tags, rollback_tags = push_docker_instance.generate_backup_mapping(
        [container_multiarch_push_item, container_signing_push_item]
    )

    assert backup_tags == {
        push_docker.PushDocker.ImageData(
            repo="some-namespace/target----repo", tag="latest-test-tag"
        ): "some-manifest-list"
    }
    assert rollback_tags == [
        push_docker.PushDocker.ImageData(repo="some-namespace/target----repo1", tag="tag1"),
        push_docker.PushDocker.ImageData(repo="some-namespace/target----repo1", tag="tag2"),
        push_docker.PushDocker.ImageData(repo="some-namespace/target----repo2", tag="tag3"),
    ]
    assert mock_get_repository_data.call_count == 3
    assert mock_get_repository_data.call_args_list[0] == mock.call("some-namespace/target----repo")
    assert mock_get_repository_data.call_args_list[1] == mock.call("some-namespace/target----repo1")
    assert mock_get_repository_data.call_args_list[2] == mock.call("some-namespace/target----repo2")

    mock_get_manifest.assert_called_once_with(
        "quay.io/some-namespace/target----repo@sha256:a1a1a1a1a1a1"
    )


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_generate_backup_mapping_server_error(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    container_signing_push_item,
):
    hub = mock.MagicMock()

    response = mock.MagicMock()
    response.status_code = 500
    mock_get_repository_data = mock.MagicMock()
    mock_get_repository_data.side_effect = [
        {"tags": {"latest-test-tag": {"manifest_digest": "sha256:a1a1a1a1a1a1"}}},
        requests.exceptions.HTTPError("server error", response=response),
        {"tags": {"some-other-tag": {"manifest_digest": "sha256:b2b2b2b2b2b2"}}},
    ]
    mock_quay_api_client.return_value.get_repository_data = mock_get_repository_data

    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    with pytest.raises(requests.exceptions.HTTPError, match=".*server error*"):
        backup_tags, rollback_tags = push_docker_instance.generate_backup_mapping(
            [container_multiarch_push_item, container_signing_push_item]
        )

    assert mock_get_repository_data.call_count == 2


@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_rollback(
    mock_quay_api_client,
    mock_quay_client,
    target_settings,
    container_multiarch_push_item,
    container_signing_push_item,
):
    hub = mock.MagicMock()
    mock_upload_manifest = mock.MagicMock()
    mock_quay_client.return_value.upload_manifest = mock_upload_manifest
    mock_delete_tag = mock.MagicMock()
    mock_quay_api_client.return_value.delete_tag = mock_delete_tag

    backup_tags = {
        push_docker.PushDocker.ImageData(
            repo="some-namespace/target----repo1", tag="1"
        ): "some-manifest-list",
        push_docker.PushDocker.ImageData(
            repo="some-namespace/target----repo2", tag="2"
        ): "other-manifest-list",
    }
    rollback_tags = [
        push_docker.PushDocker.ImageData(repo="some-namespace/target----repo3", tag="3"),
        push_docker.PushDocker.ImageData(repo="some-namespace/target----repo4", tag="4"),
    ]
    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, container_signing_push_item],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    push_docker_instance.rollback(backup_tags, rollback_tags)

    assert mock_upload_manifest.call_count == 2
    assert mock_upload_manifest.call_args_list[0] == mock.call(
        "some-manifest-list", "quay.io/some-namespace/target----repo1:1"
    )
    assert mock_upload_manifest.call_args_list[1] == mock.call(
        "other-manifest-list", "quay.io/some-namespace/target----repo2:2"
    )
    assert mock_delete_tag.call_count == 2
    assert mock_delete_tag.call_args_list[0] == mock.call("some-namespace/target----repo3", "3")
    assert mock_delete_tag.call_args_list[1] == mock.call("some-namespace/target----repo4", "4")


@mock.patch("pubtools._quay.push_docker.PushDocker.rollback")
@mock.patch("pubtools._quay.push_docker.OperatorSignatureHandler")
@mock.patch("pubtools._quay.push_docker.OperatorPusher")
@mock.patch("pubtools._quay.push_docker.ContainerSignatureHandler")
@mock.patch("pubtools._quay.push_docker.ContainerImagePusher")
@mock.patch("pubtools._quay.push_docker.PushDocker.generate_backup_mapping")
@mock.patch("pubtools._quay.push_docker.PushDocker.check_repos_validity")
@mock.patch("pubtools._quay.push_docker.PushDocker.get_operator_push_items")
@mock.patch("pubtools._quay.push_docker.PushDocker.get_docker_push_items")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_push_docker_full_success(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_docker_push_items,
    mock_get_operator_push_items,
    mock_check_repos_validity,
    mock_generate_backup_mapping,
    mock_container_image_pusher,
    mock_container_signature_handler,
    mock_operator_pusher,
    mock_operator_signature_handler,
    mock_rollback,
    target_settings,
    container_multiarch_push_item,
    container_push_item_external_repos,
    operator_push_item_ok,
):
    hub = mock.MagicMock()
    mock_push_container_images = mock.MagicMock()
    mock_container_image_pusher.return_value.push_container_images = mock_push_container_images
    mock_sign_container_images = mock.MagicMock()
    mock_container_signature_handler.return_value.sign_container_images = mock_sign_container_images
    mock_build_index_images = mock.MagicMock()
    mock_operator_pusher.return_value.build_index_images = mock_build_index_images
    mock_push_index_images = mock.MagicMock()
    mock_operator_pusher.return_value.push_index_images = mock_push_index_images
    mock_sign_operator_images = mock.MagicMock()
    mock_operator_signature_handler.return_value.sign_operator_images = mock_sign_operator_images

    mock_get_docker_push_items.return_value = [
        container_multiarch_push_item,
        container_push_item_external_repos,
    ]
    mock_get_operator_push_items.return_value = [operator_push_item_ok]
    mock_generate_backup_mapping.return_value = ({"some-key": "some-val"}, ["item1", "item2"])
    mock_build_index_images.return_value = {"v4.5": {"some": "data"}}

    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, operator_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    repos = push_docker_instance.run()

    mock_get_docker_push_items.assert_called_once_with()
    mock_get_docker_push_items.assert_called_once_with()
    mock_check_repos_validity.assert_called_once_with(
        [container_multiarch_push_item, container_push_item_external_repos],
        hub,
        target_settings,
        mock_quay_api_client.return_value,
    )
    mock_generate_backup_mapping.assert_called_once_with(
        [container_multiarch_push_item, container_push_item_external_repos]
    )
    mock_container_image_pusher.assert_called_once_with(
        [container_multiarch_push_item, container_push_item_external_repos], target_settings
    )
    mock_push_container_images.assert_called_once_with()
    mock_container_signature_handler.assert_called_once_with(
        hub, "1", target_settings, "some-target"
    )
    mock_sign_container_images.assert_called_once_with(
        [container_multiarch_push_item, container_push_item_external_repos]
    )
    mock_operator_pusher.assert_called_once_with([operator_push_item_ok], target_settings)
    mock_build_index_images.assert_called_once_with()
    mock_push_index_images.assert_called_once_with({"v4.5": {"some": "data"}})
    mock_operator_signature_handler.assert_called_once_with(
        hub, "1", target_settings, "some-target"
    )
    mock_sign_operator_images.assert_called_once_with({"v4.5": {"some": "data"}})
    mock_rollback.assert_not_called()
    assert repos == ["external/repo", "test_repo"]


@mock.patch("pubtools._quay.push_docker.PushDocker.rollback")
@mock.patch("pubtools._quay.push_docker.OperatorSignatureHandler")
@mock.patch("pubtools._quay.push_docker.OperatorPusher")
@mock.patch("pubtools._quay.push_docker.ContainerSignatureHandler")
@mock.patch("pubtools._quay.push_docker.ContainerImagePusher")
@mock.patch("pubtools._quay.push_docker.PushDocker.generate_backup_mapping")
@mock.patch("pubtools._quay.push_docker.PushDocker.check_repos_validity")
@mock.patch("pubtools._quay.push_docker.PushDocker.get_operator_push_items")
@mock.patch("pubtools._quay.push_docker.PushDocker.get_docker_push_items")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_push_docker_no_operator_push_items(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_docker_push_items,
    mock_get_operator_push_items,
    mock_check_repos_validity,
    mock_generate_backup_mapping,
    mock_container_image_pusher,
    mock_container_signature_handler,
    mock_operator_pusher,
    mock_operator_signature_handler,
    mock_rollback,
    target_settings,
    container_multiarch_push_item,
):
    hub = mock.MagicMock()
    mock_push_container_images = mock.MagicMock()
    mock_container_image_pusher.return_value.push_container_images = mock_push_container_images
    mock_sign_container_images = mock.MagicMock()
    mock_container_signature_handler.return_value.sign_container_images = mock_sign_container_images
    mock_build_index_images = mock.MagicMock()
    mock_operator_pusher.return_value.build_index_images = mock_build_index_images
    mock_push_index_images = mock.MagicMock()
    mock_operator_pusher.return_value.push_index_images = mock_push_index_images
    mock_sign_operator_images = mock.MagicMock()
    mock_operator_signature_handler.return_value.sign_operator_images = mock_sign_operator_images

    mock_get_docker_push_items.return_value = [container_multiarch_push_item]
    mock_get_operator_push_items.return_value = []
    mock_generate_backup_mapping.return_value = ({"some-key": "some-val"}, ["item1", "item2"])

    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item], hub, "1", "some-target", target_settings
    )
    repos = push_docker_instance.run()

    mock_get_docker_push_items.assert_called_once_with()
    mock_get_docker_push_items.assert_called_once_with()
    mock_check_repos_validity.assert_called_once_with(
        [container_multiarch_push_item], hub, target_settings, mock_quay_api_client.return_value
    )
    mock_generate_backup_mapping.assert_called_once_with([container_multiarch_push_item])
    mock_container_image_pusher.assert_called_once_with(
        [container_multiarch_push_item], target_settings
    )
    mock_push_container_images.assert_called_once_with()
    mock_container_signature_handler.assert_called_once_with(
        hub, "1", target_settings, "some-target"
    )
    mock_sign_container_images.assert_called_once_with([container_multiarch_push_item])
    mock_operator_pusher.assert_not_called()
    mock_build_index_images.assert_not_called()
    mock_push_index_images.assert_not_called()
    mock_operator_signature_handler.assert_not_called()
    mock_sign_operator_images.assert_not_called()
    mock_rollback.assert_not_called()
    assert repos == ["test_repo"]


@mock.patch("pubtools._quay.push_docker.PushDocker.rollback")
@mock.patch("pubtools._quay.push_docker.OperatorSignatureHandler")
@mock.patch("pubtools._quay.push_docker.OperatorPusher")
@mock.patch("pubtools._quay.push_docker.ContainerSignatureHandler")
@mock.patch("pubtools._quay.push_docker.ContainerImagePusher")
@mock.patch("pubtools._quay.push_docker.PushDocker.generate_backup_mapping")
@mock.patch("pubtools._quay.push_docker.PushDocker.check_repos_validity")
@mock.patch("pubtools._quay.push_docker.PushDocker.get_operator_push_items")
@mock.patch("pubtools._quay.push_docker.PushDocker.get_docker_push_items")
@mock.patch("pubtools._quay.push_docker.QuayClient")
@mock.patch("pubtools._quay.push_docker.QuayApiClient")
def test_push_docker_failure_rollback(
    mock_quay_api_client,
    mock_quay_client,
    mock_get_docker_push_items,
    mock_get_operator_push_items,
    mock_check_repos_validity,
    mock_generate_backup_mapping,
    mock_container_image_pusher,
    mock_container_signature_handler,
    mock_operator_pusher,
    mock_operator_signature_handler,
    mock_rollback,
    target_settings,
    container_multiarch_push_item,
    operator_push_item_ok,
):
    hub = mock.MagicMock()
    mock_push_container_images = mock.MagicMock()
    mock_push_container_images.side_effect = ValueError("Error pushing container images")
    mock_container_image_pusher.return_value.push_container_images = mock_push_container_images
    mock_sign_container_images = mock.MagicMock()
    mock_container_signature_handler.return_value.sign_container_images = mock_sign_container_images
    mock_build_index_images = mock.MagicMock()
    mock_operator_pusher.return_value.build_index_images = mock_build_index_images
    mock_push_index_images = mock.MagicMock()
    mock_operator_pusher.return_value.push_index_images = mock_push_index_images
    mock_sign_operator_images = mock.MagicMock()
    mock_operator_signature_handler.return_value.sign_operator_images = mock_sign_operator_images

    mock_get_docker_push_items.return_value = [container_multiarch_push_item]
    mock_get_operator_push_items.return_value = [operator_push_item_ok]
    mock_generate_backup_mapping.return_value = ({"some-key": "some-val"}, ["item1", "item2"])

    push_docker_instance = push_docker.PushDocker(
        [container_multiarch_push_item, operator_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    with pytest.raises(ValueError, match="Error pushing container images"):
        push_docker_instance.run()

    mock_get_docker_push_items.assert_called_once_with()
    mock_get_docker_push_items.assert_called_once_with()
    mock_check_repos_validity.assert_called_once_with(
        [container_multiarch_push_item], hub, target_settings, mock_quay_api_client.return_value
    )
    mock_generate_backup_mapping.assert_called_once_with([container_multiarch_push_item])
    mock_container_image_pusher.assert_called_once_with(
        [container_multiarch_push_item], target_settings
    )
    mock_push_container_images.assert_called_once_with()
    mock_container_signature_handler.assert_called_once_with(
        hub, "1", target_settings, "some-target"
    )
    mock_sign_container_images.assert_called_once_with([container_multiarch_push_item])
    mock_operator_pusher.assert_not_called()
    mock_build_index_images.assert_not_called()
    mock_push_index_images.assert_not_called()
    mock_operator_signature_handler.assert_not_called()
    mock_sign_operator_images.assert_not_called()
    mock_rollback.assert_called_once_with({"some-key": "some-val"}, ["item1", "item2"])


@mock.patch("pubtools._quay.push_docker.PushDocker")
def test_mod_entrypoint(
    mock_push_docker, container_multiarch_push_item, operator_push_item_ok, target_settings
):
    hub = mock.MagicMock()
    mock_run = mock.MagicMock()
    mock_run.return_value = ["repo1", "repo2"]
    mock_push_docker.return_value.run = mock_run

    repos = push_docker.mod_entry_point(
        [container_multiarch_push_item, operator_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    mock_push_docker.assert_called_once_with(
        [container_multiarch_push_item, operator_push_item_ok],
        hub,
        "1",
        "some-target",
        target_settings,
    )
    mock_run.assert_called_once_with()


@mock.patch("pubtools._quay.push_docker.PushDocker.verify_target_settings")
def test_filter_unrelated_repos(patched_verify_target_settings, container_push_item_external_repos):
    assert "test_repo" in container_push_item_external_repos.metadata["tags"]
    push_docker.PushDocker(
        [container_push_item_external_repos],
        mock.MagicMock(),
        mock.MagicMock(),
        mock.MagicMock(),
        mock.MagicMock(),
    ).filter_unrelated_repos([container_push_item_external_repos])
    assert "test_repo" not in container_push_item_external_repos.metadata["tags"]
