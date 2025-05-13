from nornir import InitNornir
from nornir_netmiko.tasks import netmiko_send_command, netmiko_send_config
from datetime import datetime
import os

def list_unique(nr, key):
    return sorted(set(h.data.get(key, "") for h in nr.inventory.hosts.values() if h.data.get(key)))

def prompt_choice(prompt, choices):
    print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        print(f"  {i}) {choice}")
    while True:
        selection = input("Select: ")
        if selection.isdigit() and 1 <= int(selection) <= len(choices):
            return choices[int(selection) - 1]

# === Load Nornir ===
nr = InitNornir(config_file="config.yaml")

# === Interactive Selection ===
roles = list_unique(nr, "role")
selected_role = prompt_choice("Choose a role", roles)

sites = list_unique(nr, "site")
selected_site = prompt_choice("Choose a site", sites)

# === Filter devices ===
filtered = nr.filter(role=selected_role, site=selected_site)
if not filtered.inventory.hosts:
    print("No devices match the selected filters.")
    exit(1)

print(f"\n✅ {len(filtered.inventory.hosts)} devices matched:")
for h in filtered.inventory.hosts.values():
    print(f"- {h.name} ({h.hostname})")

# === Confirm and continue ===
if input("\nProceed with config push? [y/N]: ").lower() != 'y':
    exit(0)

# === Load config commands ===
with open("config_commands.txt") as f:
    config_commands = [line.strip() for line in f if line.strip()]

# === Create logs ===
os.makedirs("logs", exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# === Config push task ===
def push_config(task):
    pre_cfg = task.run(task=netmiko_send_command, command_string="show running-config")

    if dry_run:
        preview_log = f"logs/{task.host.name}_preview_{timestamp}.log"
        with open(preview_log, "w") as f:
            f.write(f"# Would send to {task.host.name}:\n")
            for cmd in config_commands:
                f.write(f"{cmd}\n")
        print(f"(DRY-RUN) Saved config preview to {preview_log}")
        return

    # Save pre-change config (rollback snapshot)
    snapshot_log = f"logs/{task.host.name}_rollback_{timestamp}.log"
    with open(snapshot_log, "w") as f:
        f.write(pre_cfg.result)

    # Apply configuration
    result = task.run(task=netmiko_send_config, config_commands=config_commands)

    # Save change output
    output_log = f"logs/{task.host.name}_config_{timestamp}.log"
    with open(output_log, "w") as f:
        f.write(result.result)

# === Run task ===
results = filtered.run(task=push_config)

print(f"\n🚀 Config push complete. Logs saved to ./logs/")
