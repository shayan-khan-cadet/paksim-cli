#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  PAKSIM-CLI v8.0 - Smart OSINT Toolkit                         ║
║  Author: Shayan Khan                                           ║
║  🔒 For Educational & Security Research Only                   ║
║                                                                ║
║  Smart Mode: Enter SIM or CNIC → tool runs ALL relevant        ║
║              checks automatically (lookup + decode + phone)    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import requests
import json
import sys
import os
import argparse
import time
import re
import webbrowser
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any
import random

# ==================== LOCAL IMPORTS ====================
import sys as _sys
import os as _os

# Try multiple locations for cnic_codes_data
_cnic_paths = [
    _os.path.join(_os.path.dirname(__file__), "..", "data"),
    _os.path.join(_os.path.dirname(__file__), "data"),
    _os.path.dirname(__file__),
]
for _p in _cnic_paths:
    _p = _os.path.abspath(_p)
    if _p not in _sys.path and _os.path.exists(_os.path.join(_p, "cnic_codes_data.py")):
        _sys.path.insert(0, _p)

try:
    from cnic_codes_data import CNIC_CODES
    CNIC_DB_AVAILABLE = True
except ImportError:
    CNIC_CODES = {}
    CNIC_DB_AVAILABLE = False

try:
    from db_history import QueryDB
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

try:
    from report_export import (
        generate_report,
        sections_from_sim_result,
        sections_from_cnic_decode,
    )
    REPORT_AVAILABLE = True
except ImportError:
    REPORT_AVAILABLE = False

try:
    from phone_social_check import validate_phone, get_google_dork_links
    PHONE_AVAILABLE = True
except ImportError:
    PHONE_AVAILABLE = False


# ==================== COLORS ====================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    DARK = '\033[90m'
    ORANGE = '\033[38;5;214m'
    PINK = '\033[38;5;205m'
    GOLD = '\033[38;5;220m'
    LIME = '\033[38;5;154m'
    PURPLE = '\033[38;5;141m'
    SILVER = '\033[38;5;250m'
    GHOST = '\033[38;5;247m'


# ==================== GHOST MODE ====================
class GhostMode:
    def __init__(self):
        self.enabled = False
        self.proxies = []
        self.current_index = 0

    def toggle(self):
        self.enabled = not self.enabled
        status = f"{Colors.GREEN}👻 ACTIVE{Colors.END}" if self.enabled else f"{Colors.RED}❌ INACTIVE{Colors.END}"
        print(f"\n{Colors.YELLOW}🔄 Ghost Mode: {status}{Colors.END}")
        if self.enabled:
            print(f"{Colors.GHOST}👻 You are now invisible. Your real IP is hidden.{Colors.END}")
        else:
            print(f"{Colors.RED}⚠️ Ghost mode disabled. Your real IP is exposed.{Colors.END}")
        return self.enabled

    def fetch_proxies(self):
        proxies = [
            {"http": "http://51.158.97.93:8811", "https": "http://51.158.97.93:8811"},
            {"http": "http://51.158.113.162:8811", "https": "http://51.158.113.162:8811"},
            {"http": "http://51.158.104.236:8811", "https": "http://51.158.104.236:8811"},
            {"http": "http://51.158.100.154:8811", "https": "http://51.158.100.154:8811"},
        ]
        random.shuffle(proxies)
        self.proxies = proxies
        return self.proxies

    def get_next_proxy(self):
        if not self.enabled:
            return None
        if not self.proxies:
            self.fetch_proxies()
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_index % len(self.proxies)]
        self.current_index += 1
        return proxy


# ==================== CNIC DECODER ====================
def decode_cnic(cnic: str) -> dict:
    clean = re.sub(r'[^0-9]', '', cnic)
    if len(clean) > 13:
        clean = clean[:13]
    if len(clean) != 13:
        return {"error": f"CNIC must be 13 digits, got {len(clean)}"}

    if not CNIC_DB_AVAILABLE:
        return {"error": "CNIC database not loaded"}

    first_5 = clean[:5]
    gender_code = clean[12]
    gender = "Male" if int(gender_code) % 2 == 1 else "Female"

    result = None
    matched_length = 0
    for length in range(5, 0, -1):
        key = first_5[:length]
        if key in CNIC_CODES:
            result = CNIC_CODES[key]
            matched_length = length
            break

    if not result:
        return {
            "cnic": clean,
            "formatted": f"{clean[:5]}-{clean[5:12]}-{clean[12]}",
            "gender": gender,
            "error": f"Location code '{first_5}' not found",
        }

    codes_path = result.get("codes", [])
    full_names = result.get("full_path", "").split(" > ")
    clean_pairs = [
        (c, n) for c, n in zip(codes_path, full_names)
        if n.lower() != "empty" and n.strip()
    ]
    filtered_names = [n for c, n in clean_pairs]

    return {
        "cnic": clean,
        "formatted": f"{clean[:5]}-{clean[5:12]}-{clean[12]}",
        "gender": gender,
        "gender_code": gender_code,
        "first_5": first_5,
        "matched_digits": matched_length,
        "province": filtered_names[0] if len(filtered_names) > 0 else "N/A",
        "division": filtered_names[1] if len(filtered_names) > 1 else "N/A",
        "district": filtered_names[2] if len(filtered_names) > 2 else "N/A",
        "tehsil": filtered_names[3] if len(filtered_names) > 3 else "N/A",
        "union_council": filtered_names[4] if len(filtered_names) > 4 else "N/A",
        "full_path": " > ".join(filtered_names),
    }


# ==================== INPUT DETECTION ====================
def detect_input_type(value: str) -> str:
    """
    Detect what kind of input this is:
    - 'cnic'      → 13 digits
    - 'sim'       → 11-12 digits starting with 0 or 92
    - 'phone'     → any other phone-like number (10-15 digits)
    - 'unknown'   → anything else
    """
    clean = re.sub(r'[^0-9]', '', value)

    if len(clean) == 13:
        return "cnic"
    if 11 <= len(clean) <= 12:
        # Pakistani SIM: starts with 03 or 923
        if clean.startswith("0") or clean.startswith("92"):
            return "sim"
        return "phone"
    if 10 <= len(clean) <= 15:
        return "phone"
    return "unknown"


# ==================== HACKER ART ====================
class HackerArt:
    @staticmethod
    def banner():
        print(f"""
{Colors.RED}╔══════════════════════════════════════════════════════════════════╗
{Colors.RED}║{Colors.GOLD}   ██████╗  █████╗ ██╗  ██╗███████╗██╗███╗   ███╗    {Colors.RED}║
{Colors.RED}║{Colors.GOLD}   ██╔══██╗██╔══██╗██║ ██╔╝██╔════╝██║████╗ ████║    {Colors.RED}║
{Colors.RED}║{Colors.GOLD}   ██████╔╝███████║█████╔╝ ███████╗██║██╔████╔██║    {Colors.RED}║
{Colors.RED}║{Colors.GOLD}   ██╔═══╝ ██╔══██║██╔═██╗ ╚════██║██║██║╚██╔╝██║    {Colors.RED}║
{Colors.RED}║{Colors.GOLD}   ██║     ██║  ██║██║  ██╗███████║██║██║ ╚═╝ ██║    {Colors.RED}║
{Colors.RED}║{Colors.GOLD}   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝╚═╝     ╚═╝    {Colors.RED}║
{Colors.RED}╚══════════════════════════════════════════════════════════════════╝{Colors.END}
{Colors.CYAN}          👻 PAKSIM-CLI v8.0 - Smart OSINT Toolkit 👻{Colors.END}
{Colors.GOLD}          👨‍💻 Author: {Colors.END}{Colors.PINK}Shayan Khan{Colors.END}
{Colors.YELLOW}          🎯 \"Knowledge is power. Use it wisely.\"{Colors.END}
        """)

    @staticmethod
    def loading(text="Scanning"):
        frames = [
            "[👻□□□□□□□□□]", "[👻👻□□□□□□□□]", "[👻👻👻□□□□□□□]", "[👻👻👻👻□□□□□□]",
            "[👻👻👻👻👻□□□□□]", "[👻👻👻👻👻👻□□□□]", "[👻👻👻👻👻👻👻□□□]", "[👻👻👻👻👻👻👻👻□□]",
            "[👻👻👻👻👻👻👻👻👻□]", "[👻👻👻👻👻👻👻👻👻👻]"
        ]
        for frame in frames:
            sys.stdout.write(f"\r{Colors.GHOST}🔍 {text} {Colors.END}{Colors.CYAN}{frame}{Colors.END}")
            sys.stdout.flush()
            time.sleep(0.06)
        print()

    @staticmethod
    def ghost_effect():
        line = "".join(random.choice("👻") for _ in range(40))
        print(f"{Colors.GHOST}{line}{Colors.END}", end="\r")
        time.sleep(0.1)
        print(" " * 50, end="\r")

    @staticmethod
    def random_quote():
        quotes = [
            "You can't see me. I'm a ghost.",
            "Invisible. Untraceable. Unstoppable.",
            "Ghost mode activated. You're safe.",
            "They'll never know it was you.",
            "Operating from the shadows.",
            "No footprints. No traces.",
        ]
        return f"{Colors.GHOST}👻{Colors.END} {Colors.CYAN}{random.choice(quotes)}{Colors.END}"


# ==================== MAIN CLASS ====================
class PaksimCLI:
    VERSION = "8.0.0"
    BASE_URL = "https://paksims.info"
    SEARCH_URL = "https://paksims.info/search.php"
    AUTHOR = "Shayan Khan"

    def __init__(self):
        self.config = {
            "cookies": {
                "_ga": "GA1.1.1024773666.1782293225",
                "_ga_BH10FCDBP2": "GS2.1.s1782374087$o3$g0$t1782374087$j60$l0$h0",
            },
            "timeout": 20,
            "retry_count": 2,
            "delay": 1,
            "save_results": True,
        }
        self.session = requests.Session()
        self.home_dir = os.path.expanduser("~")
        self.config_dir = os.path.join(self.home_dir, ".paksim")
        self.results_dir = os.path.join(self.config_dir, "results")
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        self.setup_session()
        self.stats = {"total": 0, "successful": 0, "failed": 0}
        self.ghost_mode = GhostMode()
        self.current_proxy = None
        self.db = QueryDB() if DB_AVAILABLE else None

    def setup_session(self):
        self.headers = {
            "Host": "paksims.info",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://paksims.info/",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://paksims.info",
        }
        if "cookies" in self.config:
            self.session.cookies.update(self.config["cookies"])

    def validate_input(self, query: str) -> bool:
        query = query.strip()
        return bool(re.match(r"^\d{13}$", query) or re.match(r"^\d{11,15}$", query))

    def toggle_ghost(self):
        return self.ghost_mode.toggle()

    # ---------- SEARCH ----------
    def search(self, query: str, show_animation: bool = True) -> Optional[Dict[str, Any]]:
        query = query.strip()
        if not self.validate_input(query):
            print(f"{Colors.RED}✗ Invalid format.{Colors.END}")
            return None

        self.stats["total"] += 1
        if show_animation:
            HackerArt.loading(f"Targeting {query}")
        data = {"q": query}

        for attempt in range(self.config.get("retry_count", 2)):
            try:
                if show_animation:
                    print(f"{Colors.YELLOW}🎯 Attempt {attempt + 1}/{self.config.get('retry_count', 2)}...{Colors.END}")

                if self.ghost_mode.enabled:
                    proxy = self.ghost_mode.get_next_proxy()
                    if proxy:
                        self.current_proxy = proxy
                        ip = proxy.get("http", "").replace("http://", "").split(":")[0]
                        if show_animation:
                            print(f"{Colors.GHOST}👻 Routing through: {Colors.END}{Colors.CYAN}{ip}{Colors.END}")
                        self.session.proxies = proxy
                    else:
                        self.session.proxies = None
                else:
                    self.session.proxies = None

                response = self.session.post(
                    self.SEARCH_URL, headers=self.headers, data=data, timeout=15
                )

                if response.status_code == 200:
                    self.stats["successful"] += 1
                    try:
                        result = response.json()
                        if show_animation:
                            print()
                            HackerArt.ghost_effect()
                        return result
                    except Exception:
                        return {"raw": response.text[:500]}

            except requests.exceptions.ProxyError:
                self.session.proxies = None
                try:
                    response = self.session.post(
                        self.SEARCH_URL, headers=self.headers, data=data, timeout=15
                    )
                    if response.status_code == 200:
                        self.stats["successful"] += 1
                        return response.json()
                except Exception:
                    pass
            except requests.exceptions.Timeout:
                if show_animation:
                    print(f"{Colors.YELLOW}⚠️ Timeout{Colors.END}")
            except Exception as e:
                if show_animation:
                    print(f"{Colors.YELLOW}⚠️ Error: {str(e)[:60]}{Colors.END}")

            if attempt < self.config.get("retry_count", 2) - 1:
                time.sleep(self.config.get("delay", 1))

        self.stats["failed"] += 1
        return None

    # ---------- SAVE ----------
    def save_and_log(self, query: str, result: Dict, export_html: bool = False, query_type: str = None):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.results_dir, f"{query}_{timestamp}.json")

            with open(filename, "w") as f:
                json.dump(
                    {
                        "query": query,
                        "timestamp": timestamp,
                        "result": result,
                        "ghost_mode": self.ghost_mode.enabled,
                        "author": self.AUTHOR,
                    },
                    f,
                    indent=2,
                )
            print(f"{Colors.GOLD}💾 JSON: {Colors.END}{Colors.CYAN}{filename}{Colors.END}")

            if self.db:
                qtype = query_type or ("cnic" if len(query) == 13 else "sim")
                self.db.log(qtype, query, result, self.ghost_mode.enabled, success=True)
                print(f"{Colors.GOLD}📊 Logged to database{Colors.END}")

            if export_html and REPORT_AVAILABLE:
                sections = sections_from_sim_result(result, query)
                path = generate_report(
                    query_type=query_type or "sim",
                    query_value=query,
                    sections=sections,
                    ghost_mode=self.ghost_mode.enabled,
                    raw_json=result,
                )
                print(f"{Colors.GOLD}📄 HTML: {Colors.END}{Colors.CYAN}{path}{Colors.END}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ Save failed: {e}{Colors.END}")

    # ---------- DISPLAY: SIM/CNIC ----------
    def display_sim_result(self, result: Dict, query: str):
        print(f"\n{Colors.RED}╔══════════════════════════════════════════════════════════════════╗{Colors.END}")
        print(f"{Colors.RED}║{Colors.GOLD}   🎯 TARGET: {Colors.END}{Colors.CYAN}{query}{Colors.END}")
        print(f"{Colors.RED}║{Colors.GOLD}   ⏰ TIME: {Colors.END}{Colors.CYAN}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        print(f"{Colors.RED}║{Colors.GOLD}   🌐 DOMAIN: {Colors.END}{Colors.GREEN}paksims.info{Colors.END}")
        ghost = f"{Colors.GREEN}ACTIVE{Colors.END}" if self.ghost_mode.enabled else f"{Colors.RED}INACTIVE{Colors.END}"
        print(f"{Colors.RED}║{Colors.GOLD}   👻 GHOST: {Colors.END}{ghost}")
        print(f"{Colors.RED}╚══════════════════════════════════════════════════════════════════╝{Colors.END}")

        if "raw" in result:
            print(f"\n{Colors.YELLOW}📡 RAW:{Colors.END}")
            print(result["raw"])
            return False

        if "data" in result and isinstance(result["data"], list):
            total = len(result["data"])
            if total == 0:
                print(f"\n{Colors.YELLOW}⚠️  No SIM records found in database.{Colors.END}")
                return False

            cnic = result["data"][0].get("cni", "N/A")
            name = result["data"][0].get("nam", "N/A")

            print(f"\n{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗")
            print(f"{Colors.CYAN}║{Colors.GOLD}   📊 SIM REGISTRATION SUMMARY {Colors.END}")
            print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════╝{Colors.END}")
            print(f"{Colors.GREEN}├─{Colors.END} Total SIMs: {Colors.YELLOW}{total}{Colors.END}")
            print(f"{Colors.GREEN}├─{Colors.END} CNIC:       {Colors.PINK}{cnic}{Colors.END}")
            print(f"{Colors.GREEN}└─{Colors.END} Name:       {Colors.LIME}{name}{Colors.END}")

            for idx, item in enumerate(result["data"], 1):
                print(f"\n{Colors.GREEN}┌─ {Colors.CYAN}📱 SIM #{idx} of {total}{Colors.END}")
                print(f"{Colors.GREEN}├─{Colors.END} Phone:   {Colors.YELLOW}{item.get('nbr', 'N/A')}{Colors.END}")
                print(f"{Colors.GREEN}├─{Colors.END} Name:    {Colors.LIME}{item.get('nam', 'N/A')}{Colors.END}")
                print(f"{Colors.GREEN}├─{Colors.END} CNIC:    {Colors.PINK}{item.get('cni', 'N/A')}{Colors.END}")
                print(f"{Colors.GREEN}├─{Colors.END} Address: {Colors.WHITE}{item.get('adr', 'N/A')}{Colors.END}")
                print(f"{Colors.GREEN}└─{Colors.END} {Colors.DARK}{'─' * 50}{Colors.END}")

            return True
        return False

    # ---------- DISPLAY: CNIC DECODE ----------
    def display_cnic_decode(self, decoded: Dict):
        if decoded.get("error"):
            print(f"\n{Colors.RED}✗ {decoded['error']}{Colors.END}")
            return False
        print(f"\n{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗")
        print(f"{Colors.CYAN}║{Colors.GOLD}   🧬 CNIC STRUCTURAL DECODE {Colors.END}")
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════╝{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} CNIC:          {Colors.PINK}{decoded.get('formatted', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Gender:        {Colors.MAGENTA}{decoded.get('gender', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Province:      {Colors.LIME}{decoded.get('province', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Division:      {Colors.CYAN}{decoded.get('division', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} District:      {Colors.YELLOW}{decoded.get('district', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Tehsil:        {Colors.MAGENTA}{decoded.get('tehsil', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Union Council: {Colors.ORANGE}{decoded.get('union_council', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}└─{Colors.END} {Colors.DARK}{'─' * 50}{Colors.END}")
        print(f"{Colors.DARK}ℹ️  Decoded from CNIC structure (registered region, not current address){Colors.END}")
        return True

    # ---------- DISPLAY: PHONE ----------
    def display_phone_result(self, data: Dict):
        if not PHONE_AVAILABLE:
            print(f"{Colors.RED}✗ Phone module not available{Colors.END}")
            return False
        if data.get("error"):
            print(f"\n{Colors.RED}✗ {data['error']}{Colors.END}")
            return False

        print(f"\n{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗")
        print(f"{Colors.CYAN}║{Colors.GOLD}   📱 PHONE INTELLIGENCE {Colors.END}")
        print(f"{Colors.CYAN}╚══════════════════════════════════════════════════════════════════╝{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Input:         {Colors.CYAN}{data.get('input', 'N/A')}{Colors.END}")
        valid = "✅ YES" if data.get("valid") else "❌ NO"
        print(f"{Colors.GREEN}├─{Colors.END} Valid:         {Colors.LIME}{valid}{Colors.END}")
        fmt = data.get("formatted", {})
        if fmt:
            print(f"{Colors.GREEN}├─{Colors.END} E164:          {Colors.LIME}{fmt.get('e164', 'N/A')}{Colors.END}")
            print(f"{Colors.GREEN}├─{Colors.END} International: {Colors.YELLOW}{fmt.get('international', 'N/A')}{Colors.END}")
            print(f"{Colors.GREEN}├─{Colors.END} National:      {Colors.WHITE}{fmt.get('national', 'N/A')}{Colors.END}")
        if data.get("country"):
            print(f"{Colors.GREEN}├─{Colors.END} Country:       {Colors.CYAN}{data['country']}{Colors.END}")
        if data.get("region_code"):
            print(f"{Colors.GREEN}├─{Colors.END} Region:        {Colors.SILVER}{data['region_code']}{Colors.END}")

        carrier = data.get("carrier")
        if not carrier and data.get("input"):
            from phone_social_check import detect_carrier_from_prefix
            carrier = detect_carrier_from_prefix(data["input"])
        if carrier:
            print(f"{Colors.GREEN}├─{Colors.END} Carrier:       {Colors.MAGENTA}{carrier}{Colors.END}")
        if data.get("line_type"):
            print(f"{Colors.GREEN}├─{Colors.END} Line Type:     {Colors.ORANGE}{data['line_type']}{Colors.END}")
        if data.get("timezones"):
            print(f"{Colors.GREEN}├─{Colors.END} Timezone:      {Colors.SILVER}{', '.join(data['timezones'][:3])}{Colors.END}")

        links = get_google_dork_links(data.get("input", ""))
        print(f"{Colors.GREEN}├─{Colors.END} OSINT Links:")
        print(f"{Colors.GREEN}│  {Colors.END}{Colors.CYAN}WhatsApp:{Colors.END}   {Colors.DARK}{links.get('whatsapp', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}│  {Colors.END}{Colors.CYAN}Truecaller:{Colors.END} {Colors.DARK}{links.get('truecaller', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}│  {Colors.END}{Colors.CYAN}Google:{Colors.END}     {Colors.DARK}{links.get('google', 'N/A')}{Colors.END}")
        print(f"{Colors.GREEN}└─{Colors.END} {Colors.DARK}{'─' * 50}{Colors.END}")
        return True

    # ---------- SMART LOOKUP ----------
    def smart_lookup(self, value: str, export_html: bool = False):
        """
        The main entry point.
        Detects input type and runs all relevant checks automatically.
        """
        clean = re.sub(r'[^0-9]', '', value)
        input_type = detect_input_type(clean)

        print(f"\n{Colors.CYAN}🧠 Smart input detection: {Colors.GOLD}{input_type.upper()}{Colors.END}")
        print(f"{Colors.DARK}{'─' * 60}{Colors.END}")

        if input_type == "cnic":
            self._run_cnic_mode(clean, export_html)
        elif input_type == "sim":
            self._run_sim_mode(clean, export_html)
        elif input_type == "phone":
            self._run_phone_mode(clean)
        else:
            print(f"{Colors.RED}✗ Unrecognized input format{Colors.END}")

    def _run_sim_mode(self, number: str, export_html: bool = False):
        """SIM mode: lookup + offer CNIC trace + phone intel + decode"""
        # Normalize to 11-digit starting with 0
        if number.startswith("92"):
            number = "0" + number[2:]

        # 1. SIM lookup
        result = self.search(number)
        found = self.display_sim_result(result, number) if result else False

        if found and result:
            cnic = result["data"][0].get("cni", "").strip()
            self.save_and_log(number, result, export_html=export_html, query_type="sim")

            # 2. Phone intel
            if PHONE_AVAILABLE:
                print(f"\n{Colors.CYAN}🔍 Also running phone intelligence...{Colors.END}")
                v = validate_phone(number)
                self.display_phone_result(v)
                if self.db:
                    self.db.log("phone", number, v, self.ghost_mode.enabled)

            # 3. Offer CNIC trace
            if cnic and cnic != "N/A":
                self._next_action_menu(cnic, result, original_query=number)

        elif not found:
            # SIM lookup failed or no records — still show phone intel
            if PHONE_AVAILABLE:
                print(f"\n{Colors.CYAN}🔍 No SIM records — showing phone intelligence...{Colors.END}")
                v = validate_phone(number)
                self.display_phone_result(v)

    def _run_cnic_mode(self, cnic: str, export_html: bool = False):
        """CNIC mode: decode + SIM lookup automatically"""
        # 1. Structural decode (instant)
        decoded = decode_cnic(cnic)
        self.display_cnic_decode(decoded)

        # 2. SIM lookup
        print(f"\n{Colors.CYAN}🔍 Also running SIM lookup...{Colors.END}")
        result = self.search(cnic)
        found = self.display_sim_result(result, cnic) if result else False

        if found and result:
            self.save_and_log(cnic, result, export_html=export_html, query_type="cnic")
            # Offer map / ghost / etc.
            self._next_action_menu(cnic, result, original_query=cnic, is_cnic_mode=True)
        elif not found:
            # No SIM records — offer map of decoded district
            if decoded.get("district") and decoded.get("district") != "N/A":
                print(f"\n{Colors.CYAN}┌─ {Colors.GOLD}🗺️  LOCATION FROM CNIC DECODE{Colors.END}")
                print(f"{Colors.CYAN}├─{Colors.END} District: {Colors.YELLOW}{decoded['district']}{Colors.END}")
                print(f"{Colors.CYAN}└─{Colors.END} Opening map...")
                addr = f"{decoded.get('tehsil', '')}, {decoded.get('district', '')}, Pakistan"
                webbrowser.open(f"https://www.google.com/maps/search/{urllib.parse.quote(addr)}")

    def _run_phone_mode(self, number: str):
        """Phone mode: validate + intel + carrier"""
        if PHONE_AVAILABLE:
            v = validate_phone(number)
            self.display_phone_result(v)
            if self.db:
                self.db.log("phone", number, v, self.ghost_mode.enabled)

    # ---------- NEXT ACTION MENU ----------
    def _next_action_menu(self, cnic: str, result: Dict, original_query: str, is_cnic_mode: bool = False):
        """Show next-action menu after SIM/CNIC results"""
        cnic_clean = re.sub(r'[^0-9]', '', cnic)

        print(f"\n{Colors.CYAN}┌─ {Colors.GOLD}🔍 NEXT ACTIONS{Colors.END}")
        if not is_cnic_mode:
            print(f"{Colors.CYAN}├─{Colors.END} {Colors.GREEN}[{Colors.END}{Colors.GOLD}ok{Colors.END}{Colors.GREEN}]{Colors.END}      Trace all SIMs for CNIC {cnic}")
        print(f"{Colors.CYAN}├─{Colors.END} {Colors.GREEN}[{Colors.END}{Colors.GOLD}decode{Colors.END}{Colors.GREEN}]{Colors.END}  Structural CNIC decode")
        print(f"{Colors.CYAN}├─{Colors.END} {Colors.GREEN}[{Colors.END}{Colors.GOLD}phone{Colors.END}{Colors.GREEN}]{Colors.END}   Phone intelligence")
        print(f"{Colors.CYAN}├─{Colors.END} {Colors.GREEN}[{Colors.END}{Colors.GOLD}map{Colors.END}{Colors.GREEN}]{Colors.END}     Open address in Google Maps")
        print(f"{Colors.CYAN}├─{Colors.END} {Colors.GREEN}[{Colors.END}{Colors.GOLD}ghost{Colors.END}{Colors.GREEN}]{Colors.END}   Toggle Ghost Mode")
        print(f"{Colors.CYAN}└─{Colors.END} {Colors.GREEN}[{Colors.END}{Colors.GOLD}quit{Colors.END}{Colors.GREEN}]{Colors.END}    Continue / exit")

        try:
            choice = input(f"\n{Colors.YELLOW}⚡ Choice: {Colors.END}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return

        if choice == "ok" and not is_cnic_mode:
            print(f"\n{Colors.GREEN}🔍 Tracing CNIC: {cnic}{Colors.END}")
            self._run_cnic_mode(cnic_clean)
        elif choice == "decode":
            self.display_cnic_decode(decode_cnic(cnic_clean))
        elif choice == "phone":
            # Try the original query if it's a number            num = original_query
            if PHONE_AVAILABLE and re.match(r'^\+?\d+$', num):
                v = validate_phone(num)
                self.display_phone_result(v)
        elif choice == "map":
            addr = result["data"][0].get("adr", "") if result.get("data") else ""
            if addr and addr != "N/A":
                clean = addr.replace(",", " ").strip()
                webbrowser.open(f"https://www.google.com/maps/search/{urllib.parse.quote(clean)}")
                print(f"{Colors.GREEN}✅ Map opened{Colors.END}")
            else:
                print(f"{Colors.YELLOW}⚠️  No address available{Colors.END}")
        elif choice == "ghost":
            self.toggle_ghost()

    # ---------- STATS ----------
    def get_stats(self):
        ghost = f"{Colors.GREEN}👻 ACTIVE{Colors.END}" if self.ghost_mode.enabled else f"{Colors.RED}👁️ INACTIVE{Colors.END}"
        print(f"\n{Colors.CYAN}📊 SESSION STATS{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Total:    {Colors.BLUE}{self.stats['total']}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Success:  {Colors.GREEN}{self.stats['successful']}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Failed:   {Colors.RED}{self.stats['failed']}{Colors.END}")
        print(f"{Colors.GREEN}└─{Colors.END} Ghost:    {ghost}")


# ==================== DISCLAIMER ====================
def show_disclaimer():
    try:
        my_ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception:
        my_ip = "Unknown"
    disclaimer = f"""
{Colors.RED}╔══════════════════════════════════════════════════════════════════╗
{Colors.RED}║{Colors.YELLOW}                     ⚠️  LEGAL DISCLAIMER  ⚠️                    {Colors.RED}║
{Colors.RED}╚══════════════════════════════════════════════════════════════════╝{Colors.END}

{Colors.CYAN}Developer: {Colors.PINK}Shayan Khan{Colors.END}
{Colors.CYAN}Purpose:   {Colors.GREEN}Educational & Security Research{Colors.END}
{Colors.CYAN}Version:   {Colors.GOLD}8.0.0 - Smart OSINT Toolkit{Colors.END}

{Colors.GREEN}┌─ ACCEPTABLE USE{Colors.END}
{Colors.GREEN}├─{Colors.END} ✅ Use responsibly and ethically
{Colors.GREEN}├─{Colors.END} ✅ Obtain proper authorization
{Colors.GREEN}├─{Colors.END} ✅ Comply with all applicable laws
{Colors.GREEN}└─{Colors.END}

{Colors.RED}┌─ PROHIBITED{Colors.END}
{Colors.RED}├─{Colors.END} ❌ Stalking or harassment
{Colors.RED}├─{Colors.END} ❌ Unauthorized surveillance
{Colors.RED}├─{Colors.END} ❌ Identity theft or fraud
{Colors.RED}└─{Colors.END}

{Colors.YELLOW}⚠️  The author assumes NO responsibility for misuse.{Colors.END}

{Colors.MAGENTA}┌─ YOUR STATUS{Colors.END}
{Colors.MAGENTA}├─{Colors.END} IP:   {Colors.CYAN}{my_ip}{Colors.END}
{Colors.MAGENTA}└─{Colors.END} Time: {Colors.CYAN}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}

{Colors.GOLD}Press {Colors.GREEN}ENTER{Colors.WHITE} to continue...{Colors.END}
"""
    os.system("clear" if os.name == "posix" else "cls")
    print(disclaimer)
    input()


# ==================== HELP ====================
def show_commands():
    print(f"""
{Colors.RED}╔══════════════════════════════════════════════════════════════════╗
{Colors.RED}║{Colors.GOLD}              👻 PAKSIM-CLI v8.0 COMMANDS 👻                {Colors.RED}║
{Colors.RED}╚══════════════════════════════════════════════════════════════════╝{Colors.END}

{Colors.GREEN}🧠 SMART MODE (auto-detects input type):{Colors.END}
  {Colors.CYAN}track <number>{Colors.END}              Just type a SIM or CNIC
                                     → runs ALL relevant checks

{Colors.GREEN}🔍 LOOKUP:{Colors.END}
  {Colors.CYAN}-s, --sim <number>{Colors.END}       SIM lookup
  {Colors.CYAN}-c, --cnic <number>{Colors.END}      CNIC lookup

{Colors.GREEN}🧬 DECODE:{Colors.END}
  {Colors.CYAN}--decode <cnic>{Colors.END}          Structural CNIC decode

{Colors.GREEN}📱 PHONE:{Colors.END}
  {Colors.CYAN}--phone <number>{Colors.END}         Phone intelligence

{Colors.GREEN}👻 GHOST:{Colors.END}
  {Colors.CYAN}-g, --ghost{Colors.END}              Enable anonymous proxy
  {Colors.CYAN}--no-ghost{Colors.END}               Direct connection

{Colors.GREEN}💾 DATABASE:{Colors.END}
  {Colors.CYAN}--history{Colors.END}                Recent queries
  {Colors.CYAN}--search-history <term>{Colors.END}  Search past queries
  {Colors.CYAN}--db-stats{Colors.END}               Database stats
  {Colors.CYAN}--export-csv <file>{Colors.END}      Export to CSV
  {Colors.CYAN}--export-html{Colors.END}            Generate HTML report

{Colors.GREEN}📊 MISC:{Colors.END}
  {Colors.CYAN}-i, --interactive{Colors.END}        Interactive mode
  {Colors.CYAN}--stats{Colors.END}                  Session stats
  {Colors.CYAN}--version{Colors.END}                Show version
  {Colors.CYAN}--help-commands{Colors.END}          Show this menu

{Colors.GREEN}💀 EXAMPLES:{Colors.END}
  {Colors.YELLOW}track 03000000000{Colors.END}                → SIM + phone intel
  {Colors.YELLOW}track 0000000000000{Colors.END}             → CNIC decode + SIM lookup
  {Colors.YELLOW}track -s 03000000000{Colors.END}
  {Colors.YELLOW}track -g 03000000000{Colors.END}            → Ghost mode
  {Colors.YELLOW}track --decode 00000-0000000-0{Colors.END}
  {Colors.YELLOW}track --phone 03000000000{Colors.END}
""")


def show_interactive_help():
    print(f"""
{Colors.RED}╔══════════════════════════════════════════════════════════════════╗
{Colors.RED}║{Colors.GOLD}            👻 INTERACTIVE MODE COMMANDS 👻                 {Colors.RED}║
{Colors.RED}╚══════════════════════════════════════════════════════════════════╝{Colors.END}

{Colors.GREEN}🧠 SMART MODE (just type):{Colors.END}
  {Colors.YELLOW}<number>{Colors.END}                    SIM or CNIC → runs all checks

{Colors.GREEN}🏷️  PREFIXED COMMANDS:{Colors.END}
  {Colors.CYAN}sim <number>{Colors.END}              SIM lookup
  {Colors.CYAN}cnic <number>{Colors.END}             CNIC lookup
  {Colors.CYAN}decode <cnic>{Colors.END}             Structural CNIC decode
  {Colors.CYAN}phone <number>{Colors.END}            Phone intelligence

{Colors.GREEN}👻 GHOST MODE:{Colors.END}
  {Colors.CYAN}ghost{Colors.END}                     Toggle Ghost Mode ON/OFF

{Colors.GREEN}💾 DATABASE:{Colors.END}
  {Colors.CYAN}history{Colors.END}                   Show recent queries
  {Colors.CYAN}search <term>{Colors.END}             Search past queries
  {Colors.CYAN}dbstats{Colors.END}                   Database stats
  {Colors.CYAN}export <file.csv>{Colors.END}         Export history to CSV

{Colors.GREEN}📊 MISC:{Colors.END}
  {Colors.CYAN}stats{Colors.END}                     Session statistics
  {Colors.CYAN}clear{Colors.END}                     Clear screen
  {Colors.CYAN}help{Colors.END}                      Show this help
  {Colors.CYAN}quit{Colors.END} / {Colors.CYAN}exit{Colors.END}              Exit
""")


# ==================== INTERACTIVE MODE ====================
def interactive_mode(tool):
    print(f"\n{Colors.GREEN}👻 INTERACTIVE MODE - Type 'help' for commands{Colors.END}")
    print(f"{Colors.DARK}{'═' * 60}{Colors.END}\n")

    ghost = f"{Colors.GREEN}ACTIVE{Colors.END}" if tool.ghost_mode.enabled else f"{Colors.RED}INACTIVE{Colors.END}"
    print(f"{Colors.CYAN}Ghost Mode: {ghost}{Colors.END}")
    print(f"{Colors.CYAN}Domain:     paksims.info{Colors.END}")
    print(f"{Colors.CYAN}Tip:        Just type a number to run ALL checks{Colors.END}\n")

    while True:
        try:
            raw = input(f"{Colors.RED}┌─{Colors.END}{Colors.GREEN}[{Colors.END}{Colors.CYAN}paksim{Colors.END}{Colors.GREEN}]{Colors.END}\n{Colors.RED}└──╼ {Colors.END}").strip()
            if not raw:
                continue

            # Strip leading flags
            cmd = raw
            if cmd.startswith("-s ") or cmd.startswith("-c "):
                cmd = cmd[3:].strip()

            lower = cmd.lower()

            # ---- Exit ----
            if lower in ("quit", "exit", "q"):
                print(f"{Colors.GREEN}👋 Stay safe!{Colors.END}")
                break

            # ---- Help ----
            if lower == "help":
                show_interactive_help()
                continue

            # ---- Ghost ----
            if lower == "ghost":
                tool.toggle_ghost()
                continue

            # ---- Stats ----
            if lower == "stats":
                tool.get_stats()
                continue

            # ---- Clear ----
            if lower == "clear":
                os.system("clear" if os.name == "posix" else "cls")
                HackerArt.banner()
                continue

            # ---- History ----
            if lower == "history":
                if tool.db:
                    rows = tool.db.recent(20)
                    print(f"\n{Colors.CYAN}📊 Recent Queries:{Colors.END}")
                    for r in rows:
                        gh = "👻" if r["ghost_mode"] else "👁️"
                        print(f"  {gh} [{r['id']:4}] {r['timestamp'][:19]} | {r['query_type']:6} | {r['query_value']}")
                continue

            # ---- DB stats ----
            if lower in ("dbstats", "db-stats"):
                if tool.db:
                    s = tool.db.stats()
                    print(f"\n{Colors.CYAN}📊 DB STATS{Colors.END}")
                    print(f"{Colors.GREEN}├─{Colors.END} Total:      {Colors.BLUE}{s['total']}{Colors.END}")
                    print(f"{Colors.GREEN}├─{Colors.END} Successful: {Colors.GREEN}{s['successful']}{Colors.END}")
                    print(f"{Colors.GREEN}├─{Colors.END} Failed:     {Colors.RED}{s['failed']}{Colors.END}")
                    print(f"{Colors.GREEN}└─{Colors.END} By Type:    {Colors.CYAN}{s['by_type']}{Colors.END}")
                continue

            # ---- Search history ----
            if lower.startswith("search "):
                term = cmd[7:].strip()
                if tool.db:
                    rows = tool.db.search(term)
                    print(f"\n{Colors.CYAN}🔍 {len(rows)} results for '{term}':{Colors.END}")
                    for r in rows:
                        print(f"  [{r['id']:4}] {r['timestamp'][:19]} | {r['query_type']:6} | {r['query_value']}")
                continue

            # ---- Export ----
            if lower.startswith("export "):
                path = cmd[7:].strip()
                if tool.db:
                    count = tool.db.export_csv(path)
                    print(f"{Colors.GREEN}✅ Exported {count} rows to {path}{Colors.END}")
                continue

            # ---- Decode ----
            if lower.startswith("decode "):
                cnic = cmd[7:].strip()
                tool.display_cnic_decode(decode_cnic(cnic))
                if tool.db:
                    tool.db.log("decode", cnic, decode_cnic(cnic), tool.ghost_mode.enabled)
                continue

            # ---- Phone ----
            if lower.startswith("phone "):
                num = cmd[6:].strip()
                if PHONE_AVAILABLE:
                    v = validate_phone(num)
                    tool.display_phone_result(v)
                    if tool.db:
                        tool.db.log("phone", num, v, tool.ghost_mode.enabled)
                continue

            # ---- SIM prefix ----
            if lower.startswith("sim "):
                num = cmd[4:].strip()
                tool._run_sim_mode(re.sub(r'[^0-9]', '', num))
                tool.get_stats()
                continue

            # ---- CNIC prefix ----
            if lower.startswith("cnic "):
                num = cmd[5:].strip()
                tool._run_cnic_mode(re.sub(r'[^0-9]', '', num))
                tool.get_stats()
                continue

            # ---- SMART MODE: plain number ----
            if re.match(r"^\+?\d+$", cmd):
                tool.smart_lookup(cmd)
                tool.get_stats()
            else:
                print(f"{Colors.RED}✗ Unknown command. Type 'help'{Colors.END}")

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}⚠️  Interrupted{Colors.END}")
            break
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.END}")


# ==================== MAIN ====================
def main():
    args_quick = sys.argv[1:]
    skip_disclaimer = any(
        a in args_quick
        for a in ["--history", "--db-stats", "--export-csv", "--version", "--help-commands", "-h"]
    )

    if not skip_disclaimer:
        show_disclaimer()

    parser = argparse.ArgumentParser(description="PAKSIM-CLI v8.0 - Smart OSINT Toolkit")
    parser.add_argument("target", nargs="?", help="SIM or CNIC (smart mode)")
    parser.add_argument("-s", "--sim", help="SIM lookup")
    parser.add_argument("-c", "--cnic", help="CNIC lookup")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("-g", "--ghost", action="store_true", help="Enable Ghost Mode")
    parser.add_argument("--no-ghost", action="store_true", help="Disable Ghost Mode")
    parser.add_argument("--decode", help="Structural CNIC decode")
    parser.add_argument("--phone", help="Phone intelligence")
    parser.add_argument("--history", action="store_true", help="Recent queries")
    parser.add_argument("--search-history", help="Search past queries")
    parser.add_argument("--db-stats", action="store_true", help="Database stats")
    parser.add_argument("--export-csv", help="Export to CSV")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    parser.add_argument("--stats", action="store_true", help="Session stats")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--help-commands", action="store_true", help="Show commands")

    args = parser.parse_args()

    if args.version:
        print(f"PAKSIM-CLI v{PaksimCLI.VERSION} - Smart OSINT Toolkit")
        print(f"Author: {PaksimCLI.AUTHOR}")
        sys.exit(0)

    if args.help_commands:
        show_commands()
        sys.exit(0)

    # ---- DB-only ----
    if args.db_stats:
        if not DB_AVAILABLE:
            print("DB module not available")
            sys.exit(1)
        db = QueryDB()
        s = db.stats()
        print(f"\n{Colors.CYAN}📊 DATABASE STATISTICS{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Total:      {Colors.BLUE}{s['total']}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Successful: {Colors.GREEN}{s['successful']}{Colors.END}")
        print(f"{Colors.GREEN}├─{Colors.END} Failed:     {Colors.RED}{s['failed']}{Colors.END}")
        print(f"{Colors.GREEN}└─{Colors.END} By Type:    {Colors.CYAN}{s['by_type']}{Colors.END}")
        sys.exit(0)

    if args.history:
        if not DB_AVAILABLE:
            print("DB module not available")
            sys.exit(1)
        db = QueryDB()
        rows = db.recent(20)
        print(f"\n{Colors.CYAN}📊 Recent Queries:{Colors.END}")
        for r in rows:
            gh = "👻" if r["ghost_mode"] else "👁️"
            print(f"  {gh} [{r['id']:4}] {r['timestamp'][:19]} | {r['query_type']:6} | {r['query_value']}")
        sys.exit(0)

    if args.search_history:
        db = QueryDB()
        rows = db.search(args.search_history)
        print(f"\n{Colors.CYAN}🔍 Found {len(rows)} results:{Colors.END}")
        for r in rows:
            print(f"  [{r['id']:4}] {r['timestamp'][:19]} | {r['query_type']:6} | {r['query_value']}")
        sys.exit(0)

    if args.export_csv:
        db = QueryDB()
        count = db.export_csv(args.export_csv)
        print(f"{Colors.GREEN}✅ Exported {count} queries to {args.export_csv}{Colors.END}")
        sys.exit(0)

    # ---- Banner ----
    os.system("clear" if os.name == "posix" else "cls")
    HackerArt.banner()
    time.sleep(0.5)

    tool = PaksimCLI()

    if args.ghost:
        tool.toggle_ghost()
    elif args.no_ghost:
        print(f"{Colors.RED}👁️  Ghost Mode: DISABLED{Colors.END}")

    # ---- Single modes ----
    if args.decode:
        decoded = decode_cnic(args.decode)
        tool.display_cnic_decode(decoded)
        if tool.db:
            tool.db.log("decode", args.decode, decoded, tool.ghost_mode.enabled)
        sys.exit(0)

    if args.phone:
        if PHONE_AVAILABLE:
            v = validate_phone(args.phone)
            tool.display_phone_result(v)
            if tool.db:
                tool.db.log("phone", args.phone, v, tool.ghost_mode.enabled)
        sys.exit(0)

    if args.stats:
        tool.get_stats()
        sys.exit(0)

    if args.interactive:
        interactive_mode(tool)
        sys.exit(0)

    # ---- Explicit -s / -c flags ----
    if args.sim:
        tool._run_sim_mode(re.sub(r'[^0-9]', '', args.sim), export_html=args.export_html)
        tool.get_stats()
        sys.exit(0)

    if args.cnic:
        tool._run_cnic_mode(re.sub(r'[^0-9]', '', args.cnic), export_html=args.export_html)
        tool.get_stats()
        sys.exit(0)

    # ---- SMART MODE: bare positional ----
    if args.target:
        tool.smart_lookup(args.target, export_html=args.export_html)
        tool.get_stats()
        sys.exit(0)

    # ---- Nothing → interactive ----
    show_commands()
    print(f"\n{Colors.YELLOW}🚀 Starting interactive mode...{Colors.END}")
    time.sleep(1)
    interactive_mode(tool)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Interrupted{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
        sys.exit(1)
