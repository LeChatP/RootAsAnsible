import os
import argparse
from pathlib import PurePosixPath
import shutil
import uuid
import subprocess
import yaml
import logging
import json

class ColoredFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    blue = "\x1b[38;5;39m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    def format(self, record):
        if record.levelno == logging.DEBUG:
            prefix = self.grey
        elif record.levelno == logging.INFO:
            prefix = self.blue
        elif record.levelno == logging.WARNING:
            prefix = self.yellow
        elif record.levelno == logging.ERROR:
            prefix = self.red
        elif record.levelno == logging.CRITICAL:
            prefix = self.bold_red
        else:
            prefix = self.reset
            
        formatter = logging.Formatter(prefix + "%(asctime)s - %(levelname)s" + self.reset + " - %(message)s")
        return formatter.format(record)

def inject_uuids(playbook_dir):
    '''
    Inject unique UUIDs into become_flags for each task in the playbook.
    This allows for generating stable identifiers for RootAsRole tasks generation and execution.
    The identifiers will be a sha224 of the playbook_path as a -r parameter and a uuid4 as -t parameter.
    
    Traverses playbooks, roles, and imports to handle 'become' inheritance correctly.
    '''
    
    # Track processed files to avoid infinite loops and re-processing
    # Map: absolute_path -> processed_with_become (bool)
    # If we processed a file with become=False, and encounter it with become=True, we re-process.
    processed_files = {}

    def get_bool_attribute(item, key, default=False):
        val = item.get(key, default)
        if isinstance(val, str):
            return val.lower() in ('yes', 'true')
        return bool(val)

    def process_file(file_path, inherited_become=False):
        abs_path = os.path.abspath(file_path)

        if abs_path in processed_files:
            # If already processed with True, we are good (True includes False case effectively for modifications)
            if processed_files[abs_path]:
                return
            # If processed with False, but now inherited_become is False, no need to upgrade
            if not inherited_become:
                return
            # If processed with False, and now inherited_become is True, we proceed to re-scan
        
        if not os.path.exists(abs_path):
            return

        try:
            with open(abs_path, 'r') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logging.warning(f"Skipping {abs_path}: {e}")
            return

        if not isinstance(data, list):
            # Mark simple files not containing list as processed to skip later
            processed_files[abs_path] = inherited_become
            return

        # Determine if it is a playbook or a task list directly
        is_playbook = False
        import_playbook_keys = ['import_playbook', 'ansible.builtin.import_playbook']
        for entry in data:
            if isinstance(entry, dict):
                if 'hosts' in entry:
                    is_playbook = True
                    break
                # Check for any import_playbook variant
                if any(k in entry for k in import_playbook_keys):
                    is_playbook = True
                    break
        
        modified = False
        role_name = os.path.relpath(abs_path, os.path.abspath(playbook_dir))

        def process_tasks(tasks, current_context_become):
            task_modified = False
            if not isinstance(tasks, list):
                return False

            for task in tasks:
                if not isinstance(task, dict): continue

                # Determine effective become for this task
                task_become = get_bool_attribute(task, 'become', current_context_become)
                
                # Check for imports/includes
                target_file = None
                # Check standard and fully qualified names
                import_keys = [
                    'include', 'include_tasks', 'import_tasks',
                    'ansible.builtin.include', 'ansible.builtin.include_tasks', 'ansible.builtin.import_tasks'
                ]
                
                for key in import_keys:
                    if key in task:
                        val = task[key]
                        if isinstance(val, dict): val = val.get('file')
                        if isinstance(val, str) and '{{' not in val:
                            target_file = val
                        break
                
                if target_file:
                    # Resolve path relative to current file
                    child_path = os.path.join(os.path.dirname(abs_path), target_file)
                    process_file(child_path, task_become)
                
                # Handling blocks (recursion within file)
                if 'block' in task:
                    if process_tasks(task['block'], task_become):
                        task_modified = True
                    if 'rescue' in task:
                         if process_tasks(task['rescue'], task_become):
                             task_modified = True
                    if 'always' in task:
                         if process_tasks(task['always'], task_become):
                             task_modified = True

                if task.get('become_method'):
                    continue
                
                # We enforce injection if effective_become is True
                if task_become:
                    # Check if already injected
                    current_flags = task.get('become_flags', '')
                    if '-r ' in current_flags and '-t ' in current_flags:
                        continue
                        
                    unique_id = str(uuid.uuid4())
                    new_flags = f"{current_flags} -r {role_name} -t {unique_id}".strip()
                    task['become_flags'] = new_flags
                    task_modified = True
            
            return task_modified

        if is_playbook:
            for play in data:
                if not isinstance(play, dict): continue
                
                if 'import_playbook' in play:
                     val = play['import_playbook']
                     if isinstance(val, str) and '{{' not in val:
                         child_path = os.path.join(os.path.dirname(abs_path), val)
                         process_file(child_path, False)
                     continue

                p_become = get_bool_attribute(play, 'become', False)
                
                if play.get('become_method'):
                    pass 
                
                # Process roles
                if 'roles' in play:
                    for role in play['roles']:
                        role_name = None
                        role_become = p_become
                        
                        if isinstance(role, str):
                            role_name = role
                        elif isinstance(role, dict):
                            role_name = role.get('role')
                            role_become = get_bool_attribute(role, 'become', p_become)
                            
                        if role_name and '{{' not in role_name:
                             # Search locations
                             candidates = [
                                 os.path.join(os.path.dirname(abs_path), 'roles', role_name),
                                 os.path.join(playbook_dir, 'roles', role_name)
                             ]
                             for c in candidates:
                                 if os.path.isdir(c):
                                     role_tasks = os.path.join(c, 'tasks', 'main.yml')
                                     process_file(role_tasks, role_become)
                                     role_handlers = os.path.join(c, 'handlers', 'main.yml')
                                     process_file(role_handlers, role_become)
                                     break
                
                if not play.get('become_method'):
                    for section in ['pre_tasks', 'tasks', 'post_tasks', 'handlers']:
                        if section in play:
                             if process_tasks(play[section], p_become):
                                 modified = True

        else:
            # Direct task list
            if process_tasks(data, inherited_become):
                modified = True

        if modified:
            with open(abs_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        processed_files[abs_path] = inherited_become


    files_to_visit = []
    if os.path.isdir(playbook_dir):
        for root, dirs, files in os.walk(playbook_dir):
            for filename in files:
                if filename.endswith(('.yml', '.yaml')):
                    files_to_visit.append(os.path.join(root, filename))
    else:
        files_to_visit.append(playbook_dir)

    for full_path in files_to_visit:
        logging.debug(f"Processing {full_path}...")
        process_file(full_path, False)

def keep_leaf_entries(data: dict[str, str]) -> dict[str, str]:
    paths = sorted(PurePosixPath(p) for p in data)
    leaf_paths = set()

    for i, p in enumerate(paths):
        if not any(
            q.parts[:len(p.parts)] == p.parts
            for q in paths[i + 1:]
        ):
            leaf_paths.add(str(p))

    return {p: data[p] for p in leaf_paths}

def main():
    # Setup logging with colors
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # Remove default handlers if any
    if logger.hasHandlers():
        logger.handlers.clear()
    
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter())
    logger.addHandler(handler)

    # Argument parsing
    parser = argparse.ArgumentParser(description="RootAsAnsible Demonstration Script")
    parser.add_argument('--discover', action='store_true', help="Run Step 1: Generation (capable)")
    parser.add_argument('--enforce', action='store_true', help="Run Step 2-4: Policy Review & Enforcement (dosr)")
    args = parser.parse_args()

    workdir_scenario = "scenario"
    build_dir = "build"
    
    if args.discover:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
        
        logging.info("🚀 Welcome to the RootAsAnsible demonstration!")
        logging.info("ℹ️  This demo illustrates the MAPE-K fully automated loop.")
        logging.info("   Goal: Generate a least-privilege policy based on observation of a \"sandbox\".")
        
        logging.info("📦 Vendoring 'scenario' directory to 'build'...")
        # Copy content of scenario to build/
        shutil.copytree(workdir_scenario, build_dir)

        logging.info("💉 Injecting UUIDs into playbooks for tracking...")
        inject_uuids(build_dir)
        
        logging.info("🏗️  Step 1: Running playbook with 'capable' to generate policy...")
        logging.info("   (This involves building Docker images and compiling dependencies. Please provide sudo password when prompted.)")
        vendored_playbook = os.path.join("playbooks", "main.yml")

        # set pwd to build dir
        os.environ['PWD'] = os.path.abspath(build_dir)
        os.environ['ANSIBLE_BECOME_METHOD'] = "capable"
        
        try:
            subprocess.run(
                ["ansible-playbook", vendored_playbook, "-i", "inventory/hosts.yml", "-e", "@vars/vars.yml", "--become-method", "capable", "-K"],
                check=True,
                cwd=build_dir
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Playbook execution failed: {e}")
            return
        logging.info("🎉 Success! The RootAsRole policy was generated in 'templates/result.json'.")
    
    ## STEP 2 & 3
    if args.enforce:
        # Ensure environment is set up if running separately
        os.environ['PWD'] = os.path.abspath(build_dir)
        os.environ['ANSIBLE_TIMEOUT'] = "120"
        vendored_playbook = os.path.join("playbooks", "main.yml")
        vendored_scenario = os.path.join("playbooks", "scenario.yml")

        logging.info("🔍  Step 2: Policy Review (Simulated).")
        # Merge policies
        base_policy_path = os.path.join(build_dir, "templates", "sr_rootasrole.json")
        generated_policy_path = os.path.join(build_dir, "templates", "result.json")
        scenario_policy_path = os.path.join(build_dir, "templates", "sr_scenario.json")        
        # first we take the sr_scenatio.json as base
        with open(base_policy_path, 'r') as f:
            base_policy = json.load(f)
        with open(scenario_policy_path, 'r') as f:
            scenario_policy = json.load(f)
        with open(generated_policy_path, 'r') as f:
            generated_policy = json.load(f)
        ## find matching task based on purpose and push the name from generated to base
        grole_map = {r["purpose"]: r for r in generated_policy["roles"]}

        for role in scenario_policy["roles"]:
            grole = grole_map.get(role["purpose"])
            if grole:
                role["name"] = grole["name"]
            else:
                continue
            
            # Create task lookup map for current matched role
            gtask_map = {t["purpose"]: t for t in grole["tasks"]}
            
            for task in role["tasks"]:
                gtask = gtask_map.get(task["purpose"])
                if gtask:
                    task["name"] = gtask["name"]
        
        ## now we merge scenario roles to base roles 
        base_policy["roles"].extend(scenario_policy["roles"])
        
        ## finally we write the merged policy to the expected location
        merged_policy_path = os.path.join(build_dir, "templates", "result_sr_rootasrole.json")
        with open(merged_policy_path, 'w') as f:
            json.dump(base_policy, f, indent=4)
        
        logging.info("🛡️  Step 3: Pushing Policy to Host. (Plan)")
        
        enforce_playbook = os.path.join("playbooks", "enforce_rar_policy.yml")
        
        try:
            subprocess.run(
                ["ansible-playbook", enforce_playbook, "-i", "inventory/hosts.yml", "-e", "@vars/vars.yml"],
                check=True,
                cwd=build_dir
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Playbook execution failed: {e}")
            return
        
        logging.info("🏴‍☠️ Let's modify mallory role to leak passwords file to demonstrate enforcement...")
        mallory_playbook_path = os.path.join(build_dir, "roles", "mallory_net_input", "tasks", "main.yml")
        
        with open(mallory_playbook_path, 'r') as f:
            mallory_tasks = yaml.safe_load(f)

        
        mallory_tasks[-1] = {
            'name': 'Make it persistent',
            'become': True,
            'changed_when': False,
            'ansible.builtin.fetch': {
                'src': '/etc/shadow',
                'dest': '{{ template_dir }}/sudo_shadow',
                'flat': True
            },
            'ignore_errors': True
        }
                
        
        with open(mallory_playbook_path, 'w') as f:
            yaml.dump(mallory_tasks, f, default_flow_style=False, sort_keys=False)
        
        ## STEP 4
        logging.info("🎬 Step 4: Let's start scenario with sudo first, to show that the \"\"attack\"\" is successful")
        logging.info("   Re-running scenario.")
        
        os.environ['ANSIBLE_BECOME_METHOD'] = "sudo"
        
        try:
            subprocess.run(
                ["ansible-playbook", vendored_scenario, "-i", "inventory/hosts.yml", "-e", "@vars/vars.yml", "--become-method", "sudo"],
                check=True,
                cwd=build_dir
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Playbook execution failed: {e}")
            return
        
        if os.path.exists(os.path.join(build_dir, "templates", "sudo_shadow")):
            logging.info(f"⚠️  Security Breach! Mallory was able to fetch /etc/shadow using sudo! The file '{os.path.join(build_dir, "templates", "sudo_shadow")}' was created!!!")
        else:
            logging.error("❌ Unexpected: Mallory could not fetch /etc/shadow even with sudo!")
        
        logging.info("Let's modify mallory role just for using 'dosr_shadow' file name")
        mallory_tasks[-1] = {
            'name': 'Make it persistent',
            'become': True,
            'changed_when': False,
            'ansible.builtin.fetch': {
                'src': '/etc/shadow',
                'dest': '{{ template_dir }}/dosr_shadow',
                'flat': True
            },
            'ignore_errors': True
        }
        
        with open(mallory_playbook_path, 'w') as f:
            yaml.dump(mallory_tasks, f, default_flow_style=False, sort_keys=False)
        
        logging.info("🔒 Now, re-running playbook with secured 'dosr' policy")
        os.environ['ANSIBLE_BECOME_METHOD'] = "dosr"
        try:
            subprocess.run(
                ["ansible-playbook", vendored_scenario, "-i", "inventory/hosts.yml", "-e", "@vars/vars.yml", "--become-method", "dosr"],
                check=True,
                cwd=build_dir
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Playbook execution failed: {e}")
            return
        
        if os.path.exists(os.path.join(build_dir, "templates", "dosr_shadow")):
            logging.error(f"❌ Security Breach! Mallory was able to fetch /etc/shadow even with dosr! The file '{os.path.join(build_dir, "templates", "dosr_shadow")}' was created!!!")
        else:
            logging.info("✅ Enforcement Successful! Mallory could NOT fetch /etc/shadow with dosr as expected.")
        
        logging.info("✅ Enforcement Demonstration completed successfully! ✅")
        logging.info("🎉 Congratulations! You have witnessed the full MAPE-K loop with RootAsAnsible.")
        logging.info("So let's recap what happened:")
        logging.info("1️⃣  We started with a playbook running in a sandbox environment using 'capable' to observe required privileges.")
        logging.info("2️⃣  From these observations, we generated a least-privilege RootAsRole policy.")
        logging.info("3️⃣  We reviewed and pushed this policy to the host.")
        logging.info(f"4️⃣  We ran the scenario using sudo first to demonstrate the security problem, the attack was successful as the file '{os.path.join(build_dir, "templates", "sudo_shadow")}' is created with passwords in it.")
        logging.info(f"5️⃣  Finally, we re-ran the same scenario using the RootAsRole policy with the 'dosr' tool and by the task failure (and the '{os.path.join(build_dir, "templates", "dosr_shadow")}' file not present), we confirmed that the security breach was prevented.")
        logging.info("🏁 This completes the demonstration of RootAsAnsible's MAPE-K loop in action!")
        logging.info("Thank you for testing!")
    
    if not args.discover and not args.enforce:
        logging.info("No steps specified. Use --discover and/or --enforce to run the demonstration.")

if __name__ == "__main__":
    main()
