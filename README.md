<div align="center">

# 👻 PAKSIM-CLI

**Smart OSINT Toolkit for Pakistani SIM · CNIC · Phone Intelligence**

[![Version](https://img.shields.io/badge/version-8.0.0-00ff9d?style=flat-square&labelColor=0a0e14)](https://github.com/shayan-khan-cadet/paksim-cli)
[![Python](https://img.shields.io/badge/python-3.10+-00ff9d?style=flat-square&labelColor=0a0e14)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-00ff9d?style=flat-square&labelColor=0a0e14)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Kali%20%7C%20Linux-00ff9d?style=flat-square&labelColor=0a0e14)](#installation)

*A clean, fast, hacker-themed CLI for SIM/CNIC lookup, structural CNIC decode, phone intelligence, and OSINT — all in one tool.*

[**Live Web Demo**](https://shayan-khan-cadet.github.io/paksim-cli) · [**Report Bug**](https://github.com/shayan-khan-cadet/paksim-cli/issues) · [**Request Feature**](https://github.com/shayan-khan-cadet/paksim-cli/issues)

</div>

---

## ⚠️ Legal Disclaimer

> This tool is for **educational and authorized security research purposes only**.
> You must **obtain proper authorization** before querying any information.
> The author assumes **NO responsibility** for misuse.
> **Do not use** for stalking, harassment, unauthorized surveillance, or any illegal activity.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Smart Mode** | Type a number → auto-detects SIM vs CNIC → runs all relevant checks |
| 📱 **SIM/CNIC Lookup** | Query registered SIMs against any CNIC or phone number |
| 🧬 **Structural CNIC Decode** | Province → Division → District → Tehsil from the CNIC structure (700+ entries) |
| 📞 **Phone Intelligence** | Carrier, country, region, line type, timezone via Google libphonenumber |
| 👻 **Ghost Mode** | Route requests through anonymous proxies |
| 🗺️ **Address Tracing** | One-click Google Maps lookup for any address |
| 💾 **Query History** | SQLite database of every lookup — search, filter, export |
| 📄 **HTML Reports** | Generate beautiful dark-themed shareable reports |
| 🎨 **Clean UI** | Unicode box-drawing, semantic colors, minimal emoji spam |

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- `pip` and `venv`
- Linux / macOS (Kali Linux recommended)

### Quick Install

```bash
git clone https://github.com/shayan-khan-cadet/paksim-cli.git
cd paksim-cli

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python3 cli/paksim.py --help-commands
