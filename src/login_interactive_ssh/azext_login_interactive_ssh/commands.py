# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------


def load_command_table(self, _):
    """Add the login-ssh command"""
    from azure.cli.core.commands import CliCommandType
    custom_type = CliCommandType(operations_tmpl='azext_login_interactive_ssh.custom#{}')

    with self.command_group('', custom_type) as g:
        g.command('login-ssh', 'login_ssh')
