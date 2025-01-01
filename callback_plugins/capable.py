# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
DOCUMENTATION = '''
name: capable
callback_type: aggregate
requirements:
    - enable in configuration
short_description: Add information to environment variables
version_added: "2.0"  # for collections, use the collection version, not the Ansible version
description:
    - This callback just add the playbook and task name to the environment variables
'''
from ansible.plugins.callback import CallbackBase
import os

class CallbackModule(CallbackBase):
    """
    This callback module is used to detect the rights needed to execute a command
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'capable'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()

    def v2_playbook_on_task_start(self, task, is_conditional):
        os.environ['ANSIBLE_TASK'] = task.get_name()

    def v2_playbook_on_start(self):
        os.environ['ANSIBLE_PLAYBOOK'] = self.playbook_filename