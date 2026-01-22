# RootAsAnsible

This project demonstrates the integration of **RootAsRole** with Ansible, enabling **Least Privilege** management and enforcement for Ansible playbooks.

It bridges the gap between Ansible's automation and granular permission control on Linux systems.

## Overview

Ansible usually requires full `sudo` (root) access to perform configuration management. **RootAsAnsible** allows you to:

1.  **Auto-Detect Permissions**: Use the `capable` plugin to "learn" what permissions (Linux Capabilities, files, syscalls) a playbook needs by running it in a dry-run/detection mode.
2.  **Generate Policies**: Automatically create **RootAsRole** policies (Roles and Tasks) based on the detected requirements.
3.  **Enforce Least Privilege**: Execute Ansible playbooks using the `dosr` (Do Switch Role) plugin, ensuring that each task runs with *only* the specific privileges it needs, rather than full root access.

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

## Reproducibility

The following artifacts are pinned to specific versions:

| Component          | Version | Repository URL                                    | Commit ID                                  | SWHID                                                |
|--------------------|---------|---------------------------------------------------|--------------------------------------------|------------------------------------------------------|
| RootAsRole         | `3.3.2` | https://github.com/LeChatP/RootAsRole.git         | `5dfa43ca6e2551cd961348664a075ca47b1644e5` | `swh:1:rev:5dfa43ca6e2551cd961348664a075ca47b1644e5` |
| RootAsRole-capable | `3.0.0` | https://github.com/LeChatP/RootAsRole-capable.git | `8fb13559dc9698e2f181756aa6aaa2646e2a85f3` | `swh:1:rev:8fb13559dc9698e2f181756aa6aaa2646e2a85f3` |
| RootAsRole-gensr   | `0.2.0` | https://github.com/LeChatP/RootAsRole-utils.git   | `d8e4b2a943af8b000a6086bcc108a46124357671` | `swh:1:rev:d8e4b2a943af8b000a6086bcc108a46124357671` |
| bpftool            | `v7.6.0-74-g5386cfc`| https://github.com/libbpf/bpftool.git             | `5386cfcc1361cec24d51c634f76564e0762d2e22` | `swh:1:rev:5386cfcc1361cec24d51c634f76564e0762d2e22` |

Note: `bpftool` includes submodules like `libbpf` which are also pinned within its tree at the revision above.

## Prerequisites

* **Ansible** (2.8+)
* **Docker** (for the demo scenario)
* **Python** (for running the PoC)

## What does the Demo do?

Before doing the scenario, the demo will install several depedencies including RootAsRole on a Docker container.

The demo is following the MAPE-K loop:
1. **Monitor**: Uses Ansible with the `capable` plugin to monitor what permissions are needed when running a playbook that installs and configures Apache.
2. **Analyze**: Generates a RootAsRole policy based on the collected data.
3. **Plan**: Deploy the generated policy to the target system using the `rootasrole` Ansible role.
4. **Execute**: Runs the scenario first with `sudo` to demonstrate a successful attack (leaking `/etc/shadow`), then runs the same playbook using the `dosr` plugin to enforce least privilege and prevent the attack.

## How to run the Demo
1. Clone the repository:
   ```bash
   git clone https://github.com/LeChatP/RootAsAnsible.git
   cd RootAsAnsible
   ```
2. Start the demo:
   ```bash
   python main.py --discover --enforce
   ```
