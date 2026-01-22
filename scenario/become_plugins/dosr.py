# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import annotations

DOCUMENTATION = """
    name: dosr
    short_description: Substitute Role
    description:
        - This become plugin allows your remote/login user to execute commands using configured roles.
    author: Eddie Billoir
    version_added: "2.8"
    options:
        become_exe:
            description: dosr executable
            default: dosr
            ini:
              - section: privilege_escalation
                key: become_exe
              - section: dosr_become_plugin
                key: executable
            vars:
              - name: ansible_become_exe
              - name: ansible_dosr_exe
            env:
              - name: ANSIBLE_BECOME_EXE
              - name: ANSIBLE_DODOSR_EXE
            keyword:
              - name: become_exe
        become_role:
            description: Role to use
            default: ''
            ini:
              - section: privilege_escalation
                key: become_role
              - section: dosr_become_plugin
                key: role
              - section: dosr_become_plugin
                key: task
            vars:
              - name: ansible_become_role
              - name: ansible_dosr_role
            env:
              - name: ANSIBLE_BECOME_ROLE
              - name: ANSIBLE_DOSR_ROLE
            keyword:
              - name: become_role
        become_flags:
            description: Options to pass to dosr
            default: ''
            ini:
              - section: privilege_escalation
                key: become_flags
              - section: dosr_become_plugin
                key: flags
            vars:
              - name: ansible_become_flags
              - name: ansible_dosr_flags
            env:
              - name: ANSIBLE_BECOME_FLAGS
              - name: ANSIBLE_DOSR_FLAGS
            keyword:
              - name: become_flags
        become_pass:
            description: Password to pass to dosr
            required: True
            vars:
              - name: ansible_become_password
              - name: ansible_become_pass
              - name: ansible_dosr_pass
            env:
              - name: ANSIBLE_BECOME_PASS
              - name: ANSIBLE_DOSR_PASS
            ini:
              - section: dosr_become_plugin
                key: password
"""

import re
import shlex

from ansible.plugins.become import BecomeBase


class BecomeModule(BecomeBase):

    name = 'dosr'

    # messages for detecting prompted password issues
    fail = ('Permission denied')
    missing = ('Permission denied')
  
    def __init__(self):
        super(BecomeModule, self).__init__()


    def build_become_command(self, cmd, shell):
        super(BecomeModule, self).build_become_command(cmd, shell)

        self.prompt = "Password:"

        if not cmd:
            return cmd

        becomecmd = self.get_option('become_exe') or self.name

        chown_user_cmd = ''
        end_chown = ''
        flags = self.get_option('become_flags') or ''
        ## check if executed files in tmp/ansible-tmp-<timestamp>-<id> directory are owned by the become_user
        for arg in shlex.split(cmd):
          for r in re.findall(r'\/.*ansible-tmp-.*\/', arg):
              chown_user_cmd += '/usr/bin/dosr -r rar_ansible -t ansible_chown /usr/bin/chown -R "`{cmd} {flag} id -u`":"`{cmd} {flag} id -u`" "{f}"; '.format(cmd=becomecmd,flag=flags,f=r)
              end_chown += '; /usr/bin/dosr -r rar_ansible -t ansible_chown /usr/bin/chown -R "`id -u`":"`id -u`" "{}" '.format(r)
        
        return ' '.join([chown_user_cmd, becomecmd, flags, self._build_success_command(cmd, shell), end_chown])

