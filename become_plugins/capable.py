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
"""

import re
import shlex
import os

from ansible.plugins.become import BecomeBase


class BecomeModule(BecomeBase):

    name = 'sr'

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
        output = '-o /tmp/ansible_rootasrole.json'.format()
        ## check if executed files in tmp/ansible-tmp-<timestamp>-<id> directory are owned by the become_user
        for arg in shlex.split(cmd):
          for r in re.findall(r'\/.*ansible-tmp-.*\/', arg):
              chown_user_cmd += '/usr/bin/sr -r ansible -t ansible_chown /usr/bin/chown -R "`{cmd} id -u`":"`{cmd} id -u`" "{f}"; '.format(cmd=becomecmd,f=r)
              end_chown += '; /usr/bin/sr -r ansible -t ansible_chown /usr/bin/chown -R "`id -u`":"`id -u`" "{}" '.format(r)


        playbook = '-p {}' % self.get_option('become_playbook') or os.environ['ANSIBLE_PLAYBOOK'] or ''
        
        task = '-t {}' % self.get_option('become_task') or os.environ['ANSIBLE_TASK'] or ''

        
        return ' '.join([chown_user_cmd, becomecmd, output, playbook, task, self._build_success_command(cmd, shell), end_chown])
