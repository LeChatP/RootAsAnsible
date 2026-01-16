# RootAsAnsible

This project demonstrates the integration of **RootAsRole** with Ansible, enabling **Least Privilege** management and enforcement for Ansible playbooks.

It bridges the gap between Ansible's automation and granular permission control on Linux systems.

## Overview

Ansible usually requires full `sudo` (root) access to perform configuration management. **RootAsAnsible** allows you to:

1.  **Auto-Detect Permissions**: Use the `capable` plugin to "learn" what permissions (Linux Capabilities, files, syscalls) a playbook needs by running it in a dry-run/detection mode.
2.  **Generate Policies**: Automatically create **RootAsRole** policies (Roles and Tasks) based on the detected requirements.
3.  **Enforce Least Privilege**: Execute Ansible playbooks using the `dosr` (Substitute Role) plugin, ensuring that each task runs with *only* the specific privileges it needs, rather than full root access.

## Components

### 1. `rootasrole` Ansible Role
Located in `scenario/roles/rootasrole`.
This role handles the lifecycle of the RootAsRole policy engine on target nodes:
- Installs `RootAsRole`, `dosr`, and `gensr` binaries.
- Manages policies: Creating roles, defining tasks, and granting permissions to users/actors.

### 2. `capable` Become Plugin
Located in `scenario/become_plugins/capable.py`.
A "learning" mode plugin. When used as the `become_method`, it doesn't just execute the task; it uses `gensr` to trace the execution and identify necessary rights.
- **Output**: Generates a JSON policy file describing the privileges required for the task on the target host.

### 3. `dosr` Become Plugin
Located in `scenario/become_plugins/dosr.py`.
An enforcement plugin. It replaces standard `sudo`.
- **function**: Executes the Ansible module using the `dosr` command-line tool.
- **Usage**: You specify which RootAsRole "Role" and "Task" the module corresponds to, and `dosr` switches to that restricted context.

## Usage Workflow

### 1. Installation
Deploy RootAsRole to your target nodes using the included role.
```yaml
- hosts: all
  roles:
    - rootasrole
  vars:
    rootasrole_command: "install"
```

### 2. Policy Learning
Run your playbook using the `capable` become method to generate the policy.
```bash
ansible-playbook main.yml -e "ansible_become_method=capable"
```

### 3. Execution with Least Privilege
Run your playbook using the `dosr` become method, referencing the defined policies.
```yaml
- name: Install Apache
  become: true
  become_method: dosr
  become_flags: "-r deploy_apache -t install_apache2"
  ansible.builtin.apt:
    name: apache2
    state: present
```

## Prerequisites

* **Ansible** (2.8+)
* **Docker** (for the demo scenario)
* **Python** (for running the PoC)

## What does the Demo do?

Before doing the scenario, the demo will install several depedencies including RootAsRole on a Docker container.

The demo is following the MAPE-K loop:
1. **Monitor**: Uses Ansible with the `capable` plugin to monitor what permissions are needed when running a playbook that installs and configures Apache.
2. **Analyze**: Adjusts Generates a RootAsRole policy based on the collected data.
3. **Plan**: Deploy the generated policy to the target system using the `rootasrole` Ansible role.
4. **Execute**: Runs the same Ansible playbook using the `dosr` plugin to enforce least privilege.

## How to run the Demo
1. Clone the repository:
   ```bash
   git clone https://github.com/LeChatP/RootAsAnsible.git
   cd RootAsAnsible
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the demo:
   ```bash
   python demo.py
   ```