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
import os
from ansible.plugins.callback import CallbackBase
from ansible.playbook.play import Play
import yaml

FILES = set()
CAPABLE_TASKS = {}

class ElementIdentifier:
    def __init__(self, name=None, ):
        pass
    
def serialize_play(play : Play):
    data = super(Play, play).serialize()

    roles = []
    for role in play.get_roles():
        try:
            roles.append(role.serialize())
        except AttributeError:
            pass
    data['roles'] = roles
    data['included_path'] = play._included_path
    data['action_groups'] = play._action_groups
    data['group_actions'] = play._group_actions

    return data

class CallbackModule(CallbackBase):
    """
    This callback module is used to detect the rights needed to execute a command
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'capable'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        
    def v2_playbook_on_task_start(self, task, is_conditional):
        # Extract UUID from task name if present
        if task.name:
            import re
            match = re.search(r'\[id:([a-f0-9\-]+)\]', task.name)
            if match:
                uuid = match.group(1)
                # Share data via environment variable (limited scope)
                os.environ['ANSIBLE_CAPABLE_TASK_UUID'] = uuid
                # Share data via temporary file (more reliable across processes)
                with open("/tmp/ansible_capable_current_uuid", "w") as f:
                    f.write(uuid)
        
        return super().v2_playbook_on_task_start(task, is_conditional)
    
    
    
    def v2_playbook_on_start(self, playbook):
        global FILES
        global CAPABLE_TASKS
        print("PLAYBOOK STARTED")
        #entries = [ serialize_play(entry) for entry in playbook._entries if isinstance(entry, Play) ]
        #with open("playbook_copied.yml", "w") as f:
        #    f.write(yaml.dump(entries))
            
            
        FILES.update(playbook._loader._FILE_CACHE)
    
    def v2_playbook_on_stats(self, stats):
        
        
            
            
        
        return super().v2_playbook_on_stats(stats)