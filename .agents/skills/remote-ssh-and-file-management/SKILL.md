---
name: remote-ssh-and-file-management
description: |
  Instructions and commands for managing the remote Windows environment,
  executing remote commands via SSH, and transferring analysis artifacts (like PNGs, HTML reports)
  back to the local Mac using SCP.
---

# SSH and Remote File Management Skill

## Connection Parameters
* **Host IP**: `100.65.139.39`
* **SSH User**: `nejath`
* **Private Key**: `~/.ssh/id_ed25519_antigravity`
* **Remote Project Directory**: `D:\workspace\omission`
* **Remote Data Directory**: `D:/analysis/nwb/`

## Command Execution Protocol

To run commands on the remote machine, prefix with standard SSH parameters.

### 1. Activating the Virtual Environment and Running Pytest
Always run commands within the directory context and target `.venv\Scripts\python` or `.venv\Scripts\pytest` directly to ensure the correct virtual environment pathing.
```bash
ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519_antigravity nejath@100.65.139.39 "cd /d D:\workspace\omission && .venv\Scripts\python -m pytest tests/"
```

### 2. Run Python One-Liners or Scripts Remotely
```bash
ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519_antigravity nejath@100.65.139.39 "cd /d D:\workspace\omission && .venv\Scripts\python -c \"import jnwb as oa; ...\""
```

## File Management & SCP Transfers

Always transfer visualization figures, notebooks, and reports generated on the remote Windows host back to the local Mac client to embed them in local artifacts.

### 1. Download File from Windows to Mac
Run this command from the local Mac terminal:
```bash
scp -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519_antigravity nejath@100.65.139.39:D:/workspace/omission/outputs/task_01_raster.png /Users/hamednejat/.gemini/antigravity/brain/<conversation-id>/
```

### 2. Upload File from Mac to Windows
```bash
scp -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519_antigravity /local/path/file.py nejath@100.65.139.39:D:/workspace/omission/scripts/
```