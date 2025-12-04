# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------


def load_arguments(self, _):
    """Add arguments for the login-ssh command"""
    with self.argument_context('login-ssh') as c:
        c.argument('oidc_redirect_port',
                   options_list=['--port', '-p'],
                   type=int,
                   help='Port for OAuth redirect (1024-65535). Used with SSH port forwarding.',
                   required=True)

        # Add tenant argument (common use case)
        c.argument('tenant',
                   options_list=['--tenant', '-t'],
                   help='The AAD tenant. Must be provided for Microsoft Account.')
