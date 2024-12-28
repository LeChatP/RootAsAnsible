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
from ansible.plugins.callback import CallbackBase
from ansible.module_utils.common.text.converters import to_native
from ansible.errors import AnsibleError


class BecomeModule(BecomeBase):

    name = 'gensr'

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

        becomeuser = self.get_option('become_user')
        chown_user_cmd = ''
        end_chown = ''
        output = '-o /tmp/ansible_rootasrole.json'.format()
        ## check if executed files in tmp/ansible-tmp-<timestamp>-<id> directory are owned by the become_user
        for arg in shlex.split(cmd):
          for r in re.findall(r'\/.*ansible-tmp-.*\/', arg):
              chown_user_cmd += '/usr/bin/sr -r ansible -t ansible_chown /usr/bin/chown -R "`{cmd} {flag} id -u`":"`{cmd} {flag} id -u`" "{f}"; '.format(cmd=becomecmd,flag=flags,f=r)
              end_chown += '; /usr/bin/sr -r ansible -t ansible_chown /usr/bin/chown -R "`id -u`":"`id -u`" "{}" '.format(r)


        if self.get_option('become_playbook'):
            playbook = '-p {}' % self.get_option('become_playbook')
        elif 'ANSIBLE_PLAYBOOK' in os.environ:
            playbook = '-p {}' % os.environ['ANSIBLE_PLAYBOOK']
        
        if self.get_option('become_task'):
            task = '-t {}' % self.get_option('become_task')
        elif 'ANSIBLE_TASK' in os.environ:
            task += '-t {}' % os.environ['ANSIBLE_TASK']

        
        return ' '.join([chown_user_cmd, becomecmd, output, playbook, task, self._build_success_command(cmd, shell), end_chown])

class CapableCallbackModule(CallbackBase):
    """
    This callback module is used to detect the rights needed to execute a command
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'capable'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CapableCallbackModule, self).__init__()

    def v2_playbook_on_task_start(self, task, is_conditional):
        os.environ['ANSIBLE_TASK'] = task.get_name()

    def v2_playbook_on_start(self):
        os.environ['ANSIBLE_PLAYBOOK'] = self.playbook_filename