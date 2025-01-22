# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import annotations

DOCUMENTATION = """
    name: capable
    short_description: Detect all rights needed to execute a command
    description:
        - This become plugin run repeatitively commands to detect all rights needed to execute a command
        - This might not work with all commands, please check that your command is repeatable and idempotent
    author: Eddie Billoir
    version_added: "2.8"
    options:
        become_playbook:
            description: The playbook to run to detect rights
            required: False
            default: None
            type: str
        become_task:
            description: The task to run to detect rights
            required: False
            default: None
            type: str
        rootasrole_policy_output:
            description: The output file of the policy
            required: False
            default: "/tmp/capable_output.json"
            type: str
        gensr_exe:
            description: The executable to run to detect rights
            required: False
            default: "/usr/bin/gensr"
            type: str
"""

import re
import shlex
import os

from ansible.plugins.become import BecomeBase
from ansible.context import CLIARGS

class BecomeModule(BecomeBase):

    name = 'sr'

    # messages for detecting prompted password issues
    fail = ('Permission denied')
    missing = ('Permission denied')
  
    def __init__(self):
        super(BecomeModule, self).__init__()
        self.playbook_name = None
        self.task_name = None
        self.rootasrole_policy_output = None

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super().set_options(task_keys=task_keys, var_options=var_options, direct=direct)
        # Retrieve the task name from the task keys
        if task_keys and 'name' in task_keys:
            self.task_name = task_keys['name']
        
        # Retrieve the playbook name from CLIARGS or other sources
        cli_args = CLIARGS.get('playbook', None)
        if cli_args:
            # Extract the playbook name from the full path
            self.playbook_name = cli_args.split('/')[-1]
        else:
            self.playbook_name = "unknown"

        self.rootasrole_policy_output = self.get_option('rootasrole_policy_output')

    def build_become_command(self, cmd, shell):
        super(BecomeModule, self).build_become_command(cmd, shell)

        self.prompt = "Password:"

        if not cmd:
            return cmd

        becomecmd = self.get_option('become_exe') or self.name

        chown_user_cmd = ''
        end_chown = ''
        gensr_args = '-c "{}"'.format(self.get_option('rootasrole_policy_output') or self.rootasrole_policy_output or '/tmp/capable_output.json')
        ## check if executed files in tmp/ansible-tmp-<timestamp>-<id> directory are owned by the become_user
        for arg in shlex.split(cmd):
          for r in re.findall(r'\/.*ansible-tmp-.*\/', arg):
              chown_user_cmd += '/usr/bin/sr -r rar_ansible -t ansible_chown /usr/bin/chown -R "`{cmd} id -u`":"`{cmd} id -u`" "{f}"; '.format(cmd=becomecmd,f=r)
              end_chown += '; /usr/bin/sr -r rar_ansible -t ansible_chown /usr/bin/chown -R "`id -u`":"`id -u`" "{}" '.format(r)
              
        gensr_args += ' -p "{}"'.format(self.task_name)
        gensr_args += ' -t "{}"'.format(self._id)
        
        gensr_exe = '{} generate'.format(self.get_option('gensr_exe') or '/usr/bin/gensr')

        
        return ' '.join([chown_user_cmd, becomecmd, gensr_exe, gensr_args, "--", self._build_success_command(cmd, shell), end_chown])
