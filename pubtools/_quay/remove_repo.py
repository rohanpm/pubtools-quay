import logging

from .signature_remover import SignatureRemover
from .quay_api_client import QuayApiClient
from .utils.misc import (
    setup_arg_parser,
    add_args_env_variables,
    send_umb_message,
    get_internal_container_repo_name,
)

LOG = logging.getLogger()
logging.basicConfig()
LOG.setLevel(logging.INFO)

REMOVE_REPO_ARGS = {
    ("--repository",): {
        "help": "External repository to remove. Must be in format <namespace>/<repo>.",
        "required": True,
        "type": str,
    },
    ("--namespace",): {
        "help": "Internal Quay namespace in which repository resides.",
        "required": True,
        "type": str,
    },
    ("--quay-api-token",): {
        "help": "OAuth token for Quay REST API.",
        "required": False,
        "type": str,
        "env_variable": "QUAY_API_TOKEN",
    },
    ("--quay-user",): {
        "help": "Username for Quay login.",
        "required": True,
        "type": str,
    },
    ("--quay-password",): {
        "help": "Password for Quay. Can be specified by env variable QUAY_PASSWORD.",
        "required": False,
        "type": str,
        "env_variable": "QUAY_PASSWORD",
    },
    ("--pyxis-server",): {
        "help": "Pyxis service hostname",
        "required": True,
        "type": str,
    },
    ("--pyxis-krb-principal",): {
        "help": "Pyxis kerberos principal in form: name@REALM",
        "required": True,
        "type": str,
    },
    ("--pyxis-krb-ktfile",): {
        "help": "Pyxis Kerberos client keytab. Optional. Used for login if TGT is not available.",
        "required": False,
        "type": str,
    },
    ("--send-umb-msg",): {
        "help": "Flag of whether to send a UMB message",
        "required": False,
        "type": bool,
    },
    ("--umb-url",): {
        "help": "UMB URL. More than one can be specified.",
        "required": False,
        "type": str,
        "action": "append",
    },
    ("--umb-cert",): {
        "help": "Path to the UMB certificate for SSL authentication.",
        "required": False,
        "type": str,
    },
    ("--umb-client-key",): {
        "help": "Path to the UMB private key for accessing the certificate.",
        "required": False,
        "type": str,
    },
    ("--umb-ca-cert",): {
        "help": "Path to the UMB CA certificate.",
        "required": False,
        "type": str,
    },
    ("--umb-topic",): {
        "help": "UMB topic to send the message to.",
        "required": False,
        "type": str,
        "default": "VirtualTopic.eng.pub.quay_remove_repository",
    },
}


def construct_kwargs(args):
    """
    Construct a kwargs dictionary based on the entered command line arguments.

    Args:
        args (argparse.Namespace):
            Parsed command line arguments.

    Returns (dict):
        Keyword arguments for the 'remove_repository' function.
    """
    kwargs = args.__dict__

    # in args.__dict__ unspecified bool values have 'None' instead of 'False'
    for name, attributes in REMOVE_REPO_ARGS.items():
        if attributes["type"] is bool:
            bool_var = name[0].lstrip("-").replace("-", "_")
            if kwargs[bool_var] is None:
                kwargs[bool_var] = False

    # some exceptions have to be remapped
    kwargs["umb_urls"] = kwargs.pop("umb_url")

    return kwargs


def verify_remove_repo_args(repository, send_umb_msg, umb_urls, umb_cert):
    """
    Verify the presence and correctness of input parameters.

    Args:
        repository (str):
            Repository to remove.
        send_umb_msg (bool):
            Whether to send UMB messages about the untagged images.
        umb_urls ([str]):
            AMQP broker URLs to connect to.
        umb_cert (str):
            Path to a certificate used for UMB authentication.
    """
    if repository.count("/") != 1 or repository[0] == "/" or repository[-1] == "/":
        raise ValueError("Provided repository must have format <namespace>/<repo>.")

    if send_umb_msg:
        if not umb_urls:
            raise ValueError("UMB URL must be specified if sending a UMB message was requested.")
        if not umb_cert:
            raise ValueError(
                "A path to a client certificate must be provided when sending a UMB message."
            )


# TODO: integration tests
def remove_repository(
    repository,
    namespace,
    quay_api_token,
    quay_user,
    quay_password,
    pyxis_server,
    pyxis_krb_principal,
    pyxis_krb_ktfile,
    send_umb_msg=False,
    umb_urls=[],
    umb_cert=None,
    umb_client_key=None,
    umb_ca_cert=None,
    umb_topic="VirtualTopic.eng.pub.quay_remove_repository",
):
    """
    Remove Quay repository.

    Args:
        repository (str):
            External repository to remove.
        namespace (str):
            Internal Quay namespace in which repository resides..
        quay_api_token (str):
            OAuth token for authentication of Quay REST API.
        quay_user (str):
            Quay username for Docker HTTP API.
        quay_password (str):
            Quay password for Docker HTTP API.
        pyxis_server (str):
            Pyxis service hostname:
        pyxis_krb_principal (str):
            Pyxis kerberos principal in form: name@REALM.
        pyxis_krb_ktfile (str):
            Pyxis Kerberos client keytab.
        send_umb_msg (bool):
            Whether to send UMB messages about the untagged images.
        umb_urls ([str]):
            AMQP broker URLs to connect to.
        umb_cert (str):
            Path to a certificate used for UMB authentication.
        umb_client_key (str):
            Path to a client key to decrypt the certificate (if necessary).
        umb_ca_cert (str):
            Path to a CA certificate (for mutual authentication).
        umb_topic (str):
            Topic to send the UMB messages to.
    """
    verify_remove_repo_args(repository, send_umb_msg, umb_urls, umb_cert)

    LOG.info("Removing repository '{0}'".format(repository))
    quay_api_client = QuayApiClient(quay_api_token)

    sig_remover = SignatureRemover(quay_user=quay_user, quay_password=quay_password)
    sig_remover.set_quay_api_client(quay_api_client)
    sig_remover.remove_repository_signatures(
        repository, namespace, pyxis_server, pyxis_krb_principal, pyxis_krb_ktfile
    )

    internal_repo = "{0}/{1}".format(namespace, get_internal_container_repo_name(repository))
    quay_api_client.delete_repository(internal_repo)

    LOG.info("Repository has been removed")
    if send_umb_msg:
        LOG.info("Sending a UMB message")
        props = {"removed_repository": repository}
        send_umb_message(
            umb_urls,
            props,
            umb_cert,
            umb_topic,
            client_key=umb_client_key,
            ca_cert=umb_ca_cert,
        )


def remove_repository_main(sysargs=None):
    """Entrypoint for removing a repository."""
    parser = setup_arg_parser(REMOVE_REPO_ARGS)
    if sysargs:
        args = parser.parse_args(sysargs[1:])
    else:
        args = parser.parse_args()  # pragma: no cover"
    args = add_args_env_variables(args, REMOVE_REPO_ARGS)

    if not args.quay_api_token:
        raise ValueError("--quay-api-token must be specified")
    if not args.quay_password:
        raise ValueError("--quay-password must be specified")

    kwargs = construct_kwargs(args)
    remove_repository(**kwargs)
