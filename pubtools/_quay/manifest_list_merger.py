from copy import deepcopy
import logging

import requests

from .quay_client import QuayClient

LOG = logging.getLogger("PubLogger")
logging.basicConfig()
LOG.setLevel(logging.INFO)


class ManifestListMerger:
    """Class containing logic for merging manifest lists of two images."""

    def __init__(self, src_image, dest_image, quay_username=None, quay_password=None, host=None):
        """
        Initialize.

        Args:
            src_image (str):
                Address to a new image whose manifest list contains the newer data.
            dest_image (str):
                Address to an older image whose data will be overwritten.
            quay_username (str):
                Username to login to quay. If ommited, external client instance should be set.
            quay_password (str):
                Password to login to quay. If ommited, external client instance should be set.
            host (str):
                Custom hostname to connect to. If ommited, standard quay.io will be used.
        """
        self.src_image = src_image
        self.dest_image = dest_image
        if quay_username and quay_password:
            self._quay_client = QuayClient(quay_username, quay_password, host)
        else:
            self._quay_client = None

    def set_quay_client(self, quay_client):
        """
        Set client instance to be used for the HTTP API operations.

        Args:
            quay_client (QuayClient):
                Instance of QuayClient.
        """
        self._quay_client = quay_client

    def merge_manifest_lists(self):
        """Merge manifest lists and upload to Quay. Main entrypoint method."""
        if not self._quay_client:
            raise RuntimeError("QuayClient instance must be set")

        LOG.info(
            "Merging manifest lists of images '{0}' and '{1}'".format(
                self.src_image, self.dest_image
            )
        )
        src_manifest_list = self._quay_client.get_manifest(self.src_image, manifest_list=True)
        dest_manifest_list = self._quay_client.get_manifest(self.dest_image, manifest_list=True)

        missing_archs = self.get_missing_architectures(src_manifest_list, dest_manifest_list)
        new_manifest_list = self._add_missing_architectures(src_manifest_list, missing_archs)

        LOG.info("Uploading the new manifest list to '{0}'".format(self.dest_image))
        self._quay_client.upload_manifest(new_manifest_list, self.dest_image)
        LOG.info("Merging manifests lists: complete.")

    @staticmethod
    def get_missing_architectures(src_manifest_list, dest_manifest_list):
        """
        Get architectures which are missing from the new source image.

        NOTE: this method assumes that images are built only for one OS. The following logic
        would need to be overwritten if multiple OS builds started to be made.

        Args:
            src_manifest_list (dict):
                Manifest list of the source image.
            dest_manifest_list (dict):
                Manifest list of the destination image.
        Returns ([dict]):
            List of arch manifest data present in destination image but missing from source.
        """
        missing_archs = []
        missing_archs_log = []
        src_archs = [arch["platform"]["architecture"] for arch in src_manifest_list["manifests"]]

        for dest_arch_dict in dest_manifest_list["manifests"]:
            if dest_arch_dict["platform"]["architecture"] not in src_archs:
                missing_archs.append(deepcopy(dest_arch_dict))
                missing_archs_log.append(dest_arch_dict["platform"]["architecture"])

        LOG.info(
            "Architectures missing from the new image: {0}".format(", ".join(missing_archs_log))
        )
        return missing_archs

    def _add_missing_architectures(self, src_manifest_list, missing_archs):
        """
        Add missing architectures to the source manifest list.

        Args:
            src_manifest_list (dict):
                Source manifest list.
            missing_archs ([dict]):
                Manifest data of missing architectures.
        Retuns (dict):
            New manifest list containing all the architectures.
        """
        new_manifest_list = deepcopy(src_manifest_list)
        new_manifest_list["manifests"] = new_manifest_list["manifests"] + missing_archs

        return new_manifest_list

    def merge_manifest_lists_selected_architectures(self, eligible_archs):
        """
        Merge manifests lists. Only specified archs are eligible for merging.

        This is an alternate workflow used in 'tag-docker'.

        Args:
            eligible_archs ([str]):
                Archs eligible for merging with the old manifest list.
        Returns (dict):
            New manifest list.
        """
        if not self._quay_client:
            raise RuntimeError("QuayClient instance must be set")

        src_manifest_list = self._quay_client.get_manifest(self.src_image, manifest_list=True)
        # It's possible that destination doesn't exist in this workflow. ML merging logic is still
        # necessary due to only some archs being eligible
        try:
            dest_manifest_list = self._quay_client.get_manifest(self.dest_image, manifest_list=True)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                dest_manifest_list = None
            else:
                raise

        archs_to_add = []
        manifests_to_add = []
        for src_arch_dict in src_manifest_list["manifests"]:
            if src_arch_dict["platform"]["architecture"] in eligible_archs:
                manifests_to_add.append(deepcopy(src_arch_dict))
                archs_to_add.append(src_arch_dict["platform"]["architecture"])

        manifests_to_keep = []
        if dest_manifest_list:
            for dest_arch_dict in dest_manifest_list["manifests"]:
                if dest_arch_dict["platform"]["architecture"] not in archs_to_add:
                    manifests_to_keep.append(deepcopy(dest_arch_dict))

        new_manifest_list = deepcopy(src_manifest_list)
        new_manifest_list["manifests"] = manifests_to_add + manifests_to_keep

        return new_manifest_list
