#!/usr/bin/env python3
"""
Phone Intelligence - Standalone phone number analysis
Uses Google's libphonenumber for validation + carrier + region
Optional: WhatsApp existence check via wa.me, Google dorks for OSINT
"""
import re
import sys
import json
import urllib.parse
from typing import Optional, Dict, Any

try:
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone, number_type, PhoneNumberType
    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False
    print("⚠️  Install phonenumbers: pip install phonenumbers", file=sys.stderr)


# Pakistani carrier prefix mapping (first 3-4 digits after country code)
PK_CARRIERS = {
    # Jazz (Mobilink)
    "300": "Jazz", "301": "Jazz", "302": "Jazz", "303": "Jazz",
    "305": "Jazz", "306": "Jazz", "307": "Jazz", "308": "Jazz",
    "309": "Jazz", "320": "Jazz", "321": "Jazz", "322": "Jazz",
    "323": "Jazz", "324": "Jazz",
    # Zong
    "310": "Zong", "311": "Zong", "312": "Zong", "313": "Zong",
    "314": "Zong", "315": "Zong", "316": "Zong", "317": "Zong",
    "318": "Zong", "319": "Zong",
    # Telenor
    "340": "Telenor", "341": "Telenor", "342": "Telenor",
    "343": "Telenor", "344": "Telenor", "345": "Telenor",
    "346": "Telenor", "347": "Telenor", "348": "Telenor",
    # Ufone
    "330": "Ufone", "331": "Ufone", "332": "Ufone",
    "333": "Ufone", "334": "Ufone", "335": "Ufone",
    # SCOM
    "355": "SCOM",
    # Special (Warid was merged with Jazz)
    "325": "Warid (Jazz)", "326": "Warid (Jazz)", "327": "Warid (Jazz)",
}


def validate_phone(number: str, default_region: str = "PK") -> Dict[str, Any]:
    """Validate and extract all info from a phone number"""
    result = {
        "input": number,
        "valid": False,
        "possible": False,
        "formatted": {},
        "country": None,
        "carrier": None,
        "timezones": [],
        "line_type": None,
        "country_code": None,
        "national_number": None,
        "region_code": None,
        "error": None,
    }
    
    if not PHONENUMBERS_AVAILABLE:
        result["error"] = "phonenumbers library not installed"
        return result
    
    try:
        parsed = phonenumbers.parse(number, default_region)
        result["possible"] = phonenumbers.is_possible_number(parsed)
        result["valid"] = phonenumbers.is_valid_number(parsed)
        
        if result["valid"]:
            result["formatted"] = {
                "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
                "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
                "rfc3966": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.RFC3966),
            }
            
            result["country"] = geocoder.description_for_number(parsed, "en")
            result["carrier"] = carrier.name_for_number(parsed, "en")
            result["timezones"] = list(timezone.time_zones_for_number(parsed))
            result["country_code"] = parsed.country_code
            result["national_number"] = parsed.national_number
            result["region_code"] = phonenumbers.region_code_for_number(parsed)
            
            ntype = number_type(parsed)
            type_map = {
                PhoneNumberType.MOBILE: "Mobile",
                PhoneNumberType.FIXED_LINE: "Landline",
                PhoneNumberType.FIXED_LINE_OR_MOBILE: "Landline / Mobile",
                PhoneNumberType.TOLL_FREE: "Toll Free",
                PhoneNumberType.PREMIUM_RATE: "Premium Rate",
                PhoneNumberType.SHARED_COST: "Shared Cost",
                PhoneNumberType.VOIP: "VoIP",
                PhoneNumberType.PERSONAL_NUMBER: "Personal Number",
                PhoneNumberType.PAGER: "Pager",
                PhoneNumberType.UAN: "UAN",
                PhoneNumberType.VOICEMAIL: "Voicemail",
                PhoneNumberType.UNKNOWN: "Unknown",
            }
            result["line_type"] = type_map.get(ntype, "Unknown")
    
    except phonenumbers.NumberParseException as e:
        result["error"] = f"Parse error: {e}"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def detect_carrier_from_prefix(number: str) -> Optional[str]:
    """Fallback carrier detection for Pakistani numbers using prefix"""
    clean = re.sub(r'[^0-9]', '', number)
    # Handle 92XXXXXXXXXX or 0XXXXXXXXXX
    if clean.startswith("92"):
        clean = "0" + clean[2:]
    # Check first 3 digits
    prefix = clean[:3]
    return PK_CARRIERS.get(prefix)


def get_whatsapp_link(number: str) -> str:
    """Generate WhatsApp check link"""
    clean = re.sub(r'[^0-9]', '', number)
    if clean.startswith("0"):
        clean = "92" + clean[1:]
    return f"https://wa.me/{clean}"


def get_google_dork_links(number: str) -> Dict[str, str]:
    """Generate OSINT search links"""
    clean = re.sub(r'[^0-9]', '', number)
    formatted = f"+{clean}" if not clean.startswith("+") else clean
    
    return {
        "google": f"https://www.google.com/search?q={formatted}",
        "truecaller": f"https://www.truecaller.com/search/pk/{clean.lstrip('+')}",
        "facebook": f"https://www.facebook.com/search/top?q={formatted}",
        "linkedin": f"https://www.linkedin.com/search/results/all/?keywords={formatted}",
        "whatsapp": get_whatsapp_link(number),
        "telegram": f"https://t.me/{formatted}",
    }


def format_output(validation: Dict) -> str:
    """Format phone check output with hacker-style UI"""
    
    class C:
        END = '\033[0m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        WHITE = '\033[97m'
        PINK = '\033[38;5;205m'
        LIME = '\033[38;5;154m'
        GOLD = '\033[38;5;220m'
        MAGENTA = '\033[95m'
        ORANGE = '\033[38;5;214m'
        SILVER = '\033[38;5;250m'
        DARK = '\033[90m'
    
    lines = []
    lines.append(f"\n{C.CYAN}╔══════════════════════════════════════════════════════════════════╗")
    lines.append(f"{C.CYAN}║{C.GOLD}   📱 PHONE NUMBER INTELLIGENCE {C.END}")
    lines.append(f"{C.CYAN}╚══════════════════════════════════════════════════════════════════╝{C.END}")
    lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Input:{C.END}           {C.CYAN}{validation.get('input', 'N/A')}{C.END}")
    
    if validation.get("error"):
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Error:{C.END}           {C.RED}{validation['error']}{C.END}")
        lines.append(f"{C.GREEN}└─{C.END} {C.DARK}{'─'*50}{C.END}")
        return '\n'.join(lines)
    
    # Validation
    if validation.get("valid"):
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Valid:{C.END}           {C.GREEN}✅ YES{C.END}")
    elif validation.get("possible"):
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Valid:{C.END}           {C.YELLOW}⚠️  Possible{C.END}")
    else:
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Valid:{C.END}           {C.RED}❌ NO{C.END}")
    
    # Formatted numbers
    fmt = validation.get("formatted", {})
    if fmt:
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}E164:{C.END}            {C.LIME}{fmt.get('e164', 'N/A')}{C.END}")
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}International:{C.END}    {C.YELLOW}{fmt.get('international', 'N/A')}{C.END}")
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}National:{C.END}         {C.WHITE}{fmt.get('national', 'N/A')}{C.END}")
    
    # Geographic
    if validation.get("country"):
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Country:{C.END}          {C.CYAN}{validation['country']}{C.END}")
    if validation.get("region_code"):
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Region Code:{C.END}      {C.SILVER}{validation['region_code']}{C.END}")
    
    # Carrier (with fallback for PK numbers)
    carrier_name = validation.get("carrier")
    if not carrier_name:
        carrier_name = detect_carrier_from_prefix(validation.get("input", ""))
    if carrier_name:
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Carrier:{C.END}          {C.MAGENTA}{carrier_name}{C.END}")
    
    if validation.get("line_type"):
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Line Type:{C.END}        {C.ORANGE}{validation['line_type']}{C.END}")
    if validation.get("timezones"):
        tz_str = ", ".join(validation["timezones"][:3])
        lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}Timezone:{C.END}         {C.SILVER}{tz_str}{C.END}")
    
    # OSINT links
    links = get_google_dork_links(validation.get("input", ""))
    lines.append(f"{C.GREEN}├─{C.END} {C.WHITE}OSINT Links:{C.END}")
    lines.append(f"{C.GREEN}│  {C.END}{C.CYAN}WhatsApp:{C.END}   {C.DARK}{links['whatsapp']}{C.END}")
    lines.append(f"{C.GREEN}│  {C.END}{C.CYAN}Truecaller:{C.END} {C.DARK}{links['truecaller']}{C.END}")
    lines.append(f"{C.GREEN}│  {C.END}{C.CYAN}Google:{C.END}     {C.DARK}{links['google']}{C.END}")
    lines.append(f"{C.GREEN}│  {C.END}{C.CYAN}Telegram:{C.END}   {C.DARK}{links['telegram']}{C.END}")
    
    lines.append(f"{C.GREEN}└─{C.END} {C.DARK}{'─'*50}{C.END}")
    lines.append(f"{C.DARK}ℹ️  WhatsApp link opens chat — if it loads, account exists.{C.END}")
    
    return '\n'.join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 phone_social_check.py <phone_number> [region]")
        print("Example: python3 phone_social_check.py 03000000000 PK")
        sys.exit(1)
    
    number = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "PK"
    
    print(f"🔍 Analyzing: {number} (region: {region})")
    
    validation = validate_phone(number, region)
    print(format_output(validation))
    
    print(f"\n{json.dumps(validation, indent=2, ensure_ascii=False)}")
