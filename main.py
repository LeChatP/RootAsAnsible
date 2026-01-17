import os
import shutil
import uuid
import subprocess
import yaml
import logging

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

                # Injection logic
                # Skip if become_method is explicitly inherited or set locally to something else?
                # The original code skipped if p_become_method or t_become_method was set.
                # Here we assume if 'become_method' is set on task, we skip.
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

                # Normal play
                # Play become
                p_become = get_bool_attribute(play, 'become', False)
                
                # Skip if play has specific become method set? 
                # Original code: yes.
                if play.get('become_method'):
                    # We still need to process roles/imports inside, but assuming they inherit the method?
                    # If play has become_method='sudo', and we inject flags for our plugin, it breaks.
                    # So we should probably skip everything in this play regarding injection.
                    # But we SHOULD still follow imports just in case they are used elsewhere?
                    # No, if we modify file, it affects everywhere. 
                    # If a task file is used in a 'sudo' play, it shouldn't have '-r -t'.
                    # But if it is ALSO used in a 'capable' play, it NEEDS '-r -t'.
                    # This is a conflict if we modify source.
                    # Assuming we optimize for 'capable' plugin presence. 
                    # If 'sudo' sees flags, it might error.
                    # For now, let's assume we proceed but pass a 'skip_injection' flag?
                    # The prompt doesn't ask to fix this conflict, so let's stick to simple logic:
                    # If play says 'sudo', we assume tasks inside are 'sudo'. 
                    # But recursive traversal serves to find files.
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
                
                # Process tasks sections
                # If play has become_method, we might want to avoid modifications?
                # The prompt implies we want to inject when valid.
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


    # Entry point: Find all YAML files to ensure coverage,
    # but primarily process starting from potential roots to get the context right?
    # Actually, iterating all files and calling process_file(f, False) covers everything.
    # Because process_file handles idempotency and state upgrades (processed_files check).
    
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

    workdir_scenario = "scenario"
    build_dir = "build"
    
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    
    logging.info("🚀 Welcome to the RootAsAnsible demonstration!")
    logging.info("ℹ️  This demo illustrates the MAPE-K fully automated loop.")
    logging.info("   Goal: Generate least-privilege policies observing a dry-run.")
    
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
    os.environ['ANSIBLE_TIMEOUT'] = "120"
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
    logging.info("🛡️  Step 2 & 3: Policy Review and Integration (Simulated).")
    logging.info("   The policy from Step 1 would effectively be reviewed and merged.")
    
    ## STEP 4
    logging.info("🎬 Step 4: Enforcing policy with 'dosr'...")
    logging.info("   Re-running playbook to execute tasks with restricted privileges.")
    
    try:
        subprocess.run(
            ["ansible-playbook", vendored_playbook, "-i", "inventory/hosts.yml", "-e", "@vars/vars.yml", "--become-method", "dosr", "-K"],
            check=True,
            cwd=build_dir
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Playbook execution failed: {e}")
        return
    
    logging.info("✅ Demonstration completed successfully!")

if __name__ == "__main__":
    main()
