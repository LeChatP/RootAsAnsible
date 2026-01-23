# RootAsAnsible

**Artifact Submission for Prix Artefact GDR Sécurité 2026**

This project demonstrates the integration of **RootAsRole** with Ansible, enabling **Least Privilege** management and enforcement for Ansible playbooks.

It bridges the gap between Ansible's automation and granular permission control on Linux systems.

In this demonstration, you will set up an automated scenario by executing the `main.py` script. In a simulated Ansible deployment environment using containers, you will deploy a website. The deployment playbook utilizes a third-party Ansible role that is normally supposed to set up firewall rules but will actually be a Supply Chain attack. We demonstrate that the environment we developed allows generating an Ansible deployment playbook that resists this attack, unlike the current Ansible version using `sudo`. For more info see the ESORICS article.

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
| RootAsRole         | `3.3.2` | https://github.com/LeChatP/RootAsRole         | `5dfa43ca6e2551cd961348664a075ca47b1644e5` | `swh:1:rev:5dfa43ca6e2551cd961348664a075ca47b1644e5` |
| RootAsRole-capable | `3.0.0` | https://github.com/LeChatP/RootAsRole-capable | `8fb13559dc9698e2f181756aa6aaa2646e2a85f3` | `swh:1:rev:8fb13559dc9698e2f181756aa6aaa2646e2a85f3` |
| RootAsRole-gensr   | `0.2.0` | https://github.com/LeChatP/RootAsRole-gensr   | `d8e4b2a943af8b000a6086bcc108a46124357671` | `swh:1:rev:d8e4b2a943af8b000a6086bcc108a46124357671` |
| bpftool            | `v7.6.0-74-g5386cfc`| https://github.com/libbpf/bpftool             | `5386cfcc1361cec24d51c634f76564e0762d2e22` | `swh:1:rev:5386cfcc1361cec24d51c634f76564e0762d2e22` |

Note: `bpftool` includes submodules like `libbpf` which are also pinned within its tree at the revision above.

## Prerequisites

*   **Linux Host**: x86_64, Kernel $\ge$ 5.0
*   **Ansible Core**: 2.16+
*   **Docker Engine**: v25+
*   **Python**: 3.12+
*   **ssh**: Installed and configured for local connections.
*   **rsync**: Required by Ansible for file transfers.
*   **git**: For cloning repositories.
*   **Hardware**: Minimum 2 vCPUs, 8GB RAM, and 40GB free disk space (to accommodate the containerized environment and compilation).

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
   python3 main.py --clean --discover --enforce
   ```

   The script accepts optional flags:
   *   `--clean`: Cleans up any previous demo artifacts before running. Can be used after the demo to cleanup your system.
   *   `--discover`: Runs Phase 1 (Privilege Discovery).
   *   `--enforce`: Runs Phase 2 (Least Privilege Enforcement).

   
   If both flags are provided, the script executes the full workflow sequentially. Note: the enforcement phase depends on the discovery phase to setup the environment correctly.

## Detailed Workflow

The demo follows a structured process:

1.  **Environment Setup**: Initializes the test environment by vendoring dependencies and creating local Docker containers.
2.  **Learning Phase**: Runs the playbook with `ansible_become_method=capable`. It verifies the generation of a `result.json` policy file, confirming that granular permissions were automatically extracted.
3.  **Policy Planification**: Edits the generated policy to produce a valid enforcement policy (fixing user/group identifiers, sanitizing paths).
4.  **Attack Simulation**:
    *   **Vulnerable Execution**: Runs the scenario with standard `sudo`. Confirms that a supply-chain attack (exfiltrating `/etc/shadow`) succeeds.
    *   **Secured Execution**: Runs the scenario with **RootAsAnsible** (`dosr`). Confirms that the malicious task fails due to lack of privileges, while legitimate tasks proceed.

## Check

To validate the results against the paper's claims:

**Claim 1: Automated Discovery**
*   After the "Learning Phase", ensure that the `result.json` file has been created.
*   Inspect the JSON content to confirm it contains fine-grained permissions (specific capabilities, file paths) rather than a blanket root access.

**Claim 2: Least Privilege Enforcement**
*   **Vulnerable Execution**: Verify in the logs that the task named "Make it persistent" succeeded when run with `sudo`. The password file (`/etc/shadow`) should be present in the build/templates/sudo_shadow file.
*   **Secured Execution**: Verify that the same "Make it persistent" **FAILED** when run with `dosr`. The Ansible output should report an error (e.g., `"Permission denied"`), confirming the attack was blocked. Also check that the `/etc/shadow` file is **NOT** present in the build/templates/dosr_shadow file.
*   **Functionality**: Confirm that legitimate tasks (e.g., "Install apache2") succeeded in the `dosr` run, proving that legitimate functionality is preserved.

## Reuse

To apply RootAsAnsible to your own playbooks:

1.  Modify the `scenario.yml` playbook in the `playbooks/` directory to push your own tasks.
2.  Modify the `main.py` script to simulate the policy modification step (policy refinement is currently a manual/scripted step).
3.  Run the `main.py` script to execute both learning and enforcement phases.

## Limitations

*   **Dynamic Analysis**: The learning mode only observes privileges for executed code paths. Conditional tasks skipped during training won't be covered in the policy.
*   **Policy Refinement**: The generated policy requires manual review and adjustment (e.g., fixing specific user IDs) before enforcement.
*   **Vendoring**: Task labeling relies on specific assumptions; complex playbooks might require manual adjustments for correct policy generation.

## License

This project and its components are open-source software. To balance freedom and flexibility, we use a dual licensing strategy:

*   **GPLv3**: Applied to the Ansible collection (**RootAsAnsible**), the analysis tool (**gensr**), and the monitoring tool (**capable**). This ensures that the core tooling and any derivatives remain free and open source, promoting community contribution and transparency.
*   **LGPLv3**: Applied to the core enforcement engine (**RootAsRole**). This less restrictive license allows organizations to develop and link proprietary, business-spercific plugins (e.g., custom authentication or audit modules) without being required to release their internal source code.
