import logging
import json
import tempfile

from .utils.misc import get_internal_container_repo_name, run_entrypoint
from .quay_api_client import QuayApiClient
from .quay_client import QuayClient

LOG = logging.getLogger("PubLogger")
logging.basicConfig()
LOG.setLevel(logging.INFO)


class SignatureRemover:
    """Class used for finding the signatures that should be removed and removing them."""

    MAX_MANIFEST_DIGESTS_PER_SEARCH_REQUEST = 50

    def __init__(self, quay_api_token=None, quay_user=None, quay_password=None, quay_host=None):
        """
        Initialize.

        Args:
            quay_api_token (str):
                Authentication token for Quay REST API.
            quay_user (str):
                User name for Quay Docker registry API.
            quay_password (str):
                Password for Quay Docker registry API.
            quay_host (str):
                Quay base host URL. Defaults to 'quay.io'.
        """
        self.quay_host = quay_host.rstrip("/") if quay_host else "quay.io"
        self.quay_api_token = quay_api_token
        self.quay_user = quay_user
        self.quay_password = quay_password

        self._quay_client = None
        self._quay_api_client = None

    @property
    def quay_api_client(self):
        """Create and access QuayApiClient."""
        if self._quay_api_client is None:
            if not self.quay_api_token:
                raise ValueError(
                    "No instance of QuayApiClient is available. Please provide "
                    "'quay_api_token' or set the instance via 'set_quay_api_client'"
                )

            self._quay_api_client = QuayApiClient(self.quay_api_token, self.quay_host)
        return self._quay_api_client

    def set_quay_api_client(self, quay_api_client):
        """
        Set a QuayApiClient instance.

        Args:
            quay_api_client (QuayApiClient):
                QuayApiClient instance.
        """
        self._quay_api_client = quay_api_client

    @property
    def quay_client(self):
        """Create and access QuayClient."""
        if self._quay_client is None:
            if not self.quay_user or not self.quay_password:
                raise ValueError(
                    "No instance of QuayClient is available. Please provide "
                    "'quay_user' and 'quay_password' or set the instance via 'set_quay_client'"
                )

            self._quay_client = QuayClient(self.quay_user, self.quay_password, self.quay_host)
        return self._quay_client

    def set_quay_client(self, quay_client):
        """
        Set a QuayClient instance.

        Args:
            quay_client (QuayClient):
                QuayClient instance.
        """
        self._quay_client = quay_client

    def get_signatures_from_pyxis(
        self,
        manifest_digests,
        pyxis_server,
        pyxis_krb_principal,
        pyxis_krb_ktfile=None,
    ):
        """
        Get existing signatures from Pyxis based on the specified criteria (currently only digests).

        NOTE: In the current implementation, only manifest digests are being used to search for
        existing signatures. Also, the search is performed in chunks, their size being limited by
        MAX_MANIFEST_DIGESTS_PER_SEARCH_REQUEST.

        NOTE: This method is copied from SignatureHandler, although it doesn't utilize
        'target_settings' in order to be more versatile.

        Args:
            manifest_digests ([str]):
                Digests for which to return signatures.
            pyxis_server (str):
                URL of the Pyxis service.
            pyxis_krb_principal (str):
                Kerberos principal to use for Pyxis authentication.
            pyxis_krb_ktfile (str|None):
                Path to Kerberos keytab file. Optional

            Yields (dict):
                Existing signatures as returned by Pyxis based on specified criteria. The returned
                sturcture is an iterator to reduce memory requirements.
        """
        chunk_size = self.MAX_MANIFEST_DIGESTS_PER_SEARCH_REQUEST

        for chunk_start in range(0, len(manifest_digests), chunk_size):
            chunk = manifest_digests[chunk_start : chunk_start + chunk_size]  # noqa: E203

            args = [
                "--pyxis-server",
                pyxis_server,
                "--pyxis-krb-principal",
                pyxis_krb_principal,
            ]
            if pyxis_krb_ktfile:
                args += ["--pyxis-krb-ktfile", pyxis_krb_ktfile]
            if manifest_digests:
                args += ["--manifest-digest", ",".join(chunk)]

            env_vars = {}
            chunk_results = run_entrypoint(
                ("pubtools-pyxis", "console_scripts", "pubtools-pyxis-get-signatures"),
                "pubtools-pyxis-get-signatures",
                args,
                env_vars,
            )
            for result in chunk_results:
                yield result

    def remove_signatures_from_pyxis(
        self, signatures_to_remove, pyxis_server, pyxis_krb_principal, pyxis_krb_ktfile=None
    ):
        """
        Remove signatures from Pyxis by using a pubtools-pyxis entrypoint.

        Args:
            signatures_to_remove ([str]):
                List of signature ids to be removed.
            pyxis_server (str):
                URL of the Pyxis service.
            pyxis_krb_principal (str):
                Kerberos principal to use for Pyxis authentication.
            pyxis_krb_ktfile (str|None):
                Path to Kerberos keytab file. Optional
        """
        LOG.info("Removing outdated signatures from pyxis")

        args = [
            "--pyxis-server",
            pyxis_server,
            "--pyxis-krb-principal",
            pyxis_krb_principal,
        ]
        if pyxis_krb_ktfile:
            args += ["--pyxis-krb-ktfile", pyxis_krb_ktfile]
        with tempfile.NamedTemporaryFile(mode="w") as temp:
            json.dump(signatures_to_remove, temp)
            temp.flush()

            args += ["--ids", "@%s" % temp.name]

            env_vars = {}
            run_entrypoint(
                ("pubtools-pyxis", "console_scripts", "pubtools-pyxis-delete-signatures"),
                "pubtools-pyxis-delete-signatures",
                args,
                env_vars,
            )

    def get_repository_digests(self, repository):
        """
        Get all digests of all images in a given repository.

        NOTE: Digests of manifest lists are not returned, as signing is not performed on them.

        Args:
            repository (str):
                Full Quay repository, including namespace.
        Returns ([str]):
            Digests of all images in a given repo.
        """
        full_repo = "{0}/{1}".format(self.quay_host, repository)
        digests = []
        repo_data = self.quay_api_client.get_repository_data(repository)

        for tag, tag_data in sorted(repo_data["tags"].items()):
            # if 'image_id' is set, the image is NOT a multiarch manifest list
            # we want to include the digest in this case
            if tag_data["image_id"] is not None:
                digests.append(tag_data["manifest_digest"])
            # If manifest list, we need to get digests of all archs
            else:
                image = "{0}:{1}".format(full_repo, tag)
                manifest_list = self.quay_client.get_manifest(image, manifest_list=True)
                for manifest in manifest_list["manifests"]:
                    digests.append(manifest["digest"])

        return sorted(list(set(digests)))

    def remove_repository_signatures(
        self, repository, namespace, pyxis_server, pyxis_krb_principal, pyxis_krb_ktfile=None
    ):
        """
        Remove all signatures of all images in a given Quay repository.

        Args:
            repository (str):
                External name for a repository whose signatures should be removed.
            namespace (str):
                Quay namespace in which the repository resides.
            pyxis_server (str):
                URL of the Pyxis service.
            pyxis_krb_principal (str):
                Kerberos principal to use for Pyxis authentication.
            pyxis_krb_ktfile (str|None):
                Path to Kerberos keytab file. Optional
        """
        LOG.info("Removing signatures of all images of repository '{0}'".format(repository))

        internal_repo = "{0}/{1}".format(namespace, get_internal_container_repo_name(repository))
        remove_signature_ids = []
        digests = self.get_repository_digests(internal_repo)

        for signature in self.get_signatures_from_pyxis(
            digests, pyxis_server, pyxis_krb_principal, pyxis_krb_ktfile
        ):
            if signature["repository"] == repository:
                remove_signature_ids.append(signature["_id"])

        if len(remove_signature_ids) > 0:
            LOG.info("{0} signatures will be removed".format(len(remove_signature_ids)))

            self.remove_signatures_from_pyxis(
                remove_signature_ids, pyxis_server, pyxis_krb_principal, pyxis_krb_ktfile
            )
        else:
            LOG.info("No signatures need to be removed")
