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
        become_exe:
            description: gensr executable
            default: gensr
            ini:
              - section: privilege_escalation
                key: become_exe
              - section: gensr_become_plugin
                key: executable
            vars:
              - name: ansible_become_exe
              - name: ansible_gensr_exe
            env:
              - name: ANSIBLE_BECOME_EXE
              - name: ANSIBLE_GENSR_EXE
            keyword:
              - name: become_exe
        become_flags:
            description: Options to pass to gensr
            default: ''
            ini:
              - section: privilege_escalation
                key: become_flags
              - section: gensr_become_plugin
                key: flags
            vars:
              - name: ansible_become_flags
              - name: ansible_gensr_flags
            env:
              - name: ANSIBLE_BECOME_FLAGS
              - name: ANSIBLE_GENSR_FLAGS
            keyword:
              - name: become_flags
        become_pass:
            description: Password to pass to gensr
            required: True
            vars:
              - name: ansible_become_password
              - name: ansible_become_pass
              - name: ansible_gensr_pass
            env:
              - name: ANSIBLE_BECOME_PASS
              - name: ANSIBLE_GENSR_PASS
            ini:
              - section: gensr_become_plugin
                key: password
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

import os

from ansible.plugins.become import BecomeBase
from ansible.context import CLIARGS

DOSR_EXE = '/usr/bin/dosr'

class BecomeModule(BecomeBase):

    name = 'gensr'

    # messages for detecting prompted password issues
    fail = ('Permission denied')
    missing = ('Permission denied')
  
    def __init__(self):
        super(BecomeModule, self).__init__()
        self.playbook_name = os.path.realpath(CLIARGS.get('args', None)[0])
        self.task_name = None
        self.rootasrole_policy_output = None

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super().set_options(task_keys=task_keys, var_options=var_options, direct=direct)
        # Retrieve the task name from the task keys
        if task_keys and 'name' in task_keys:
            self.task_name = task_keys['name']
        self.rootasrole_policy_output = self.get_option('rootasrole_policy_output')

    def build_become_command(self, cmd, shell):
        super(BecomeModule, self).build_become_command(cmd, shell)

        self.prompt = "Password:"

        if not cmd:
            return cmd

        becomecmd = '/usr/bin/dosr -r rar_ansible -t generate_rar'

        gensr_cmd = '{} generate {} -p "{}" -c "{}"'.format(
            self.get_option("become_exe"), 
            self.get_option('become_flags') or '', 
            self.task_name,
            self.get_option('rootasrole_policy_output') or self.rootasrole_policy_output or '/tmp/capable_output.json' )
        
        return ' '.join([ becomecmd, gensr_cmd, "--", self._build_success_command(cmd, shell)])
