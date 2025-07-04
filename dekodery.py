import os
import datetime
import configparser
import requests
import time
from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectTooManyRequestsError

def loguj(msg, dopisek="", ini_path=None):
    """Simple function for logging messages to a file or console."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {dopisek}: {msg}"
    if ini_path:
        cfg = configparser.ConfigParser()
        cfg.read(ini_path, encoding='utf-8')
        try:
            # Corrected log path
            base_dir = os.path.dirname(os.path.dirname(ini_path)) # goes to app folder
            log_dir = os.path.join(base_dir, 'data', 'log')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, cfg.get('PROGRAM', 'nazwa_pliku_log', fallback='fitogar_log.txt'))
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return
        except Exception as e:
            print(f"LOG WRITE ERROR: {e}")
            pass
    print(line)

def find_fitogar_weight(pakiety, min_stable=29, on_update=None):
    """
    IMPROVED VERSION: Processes a list of packets to find the weight and check stability,
    ignoring the first two bytes of the packet.
    """
    if not pakiety: return
    
    packet_hex = pakiety[-1]
    pkt_hex = packet_hex.replace(' ', '').lower()
    if len(pkt_hex) < 22: return
    try:
        data_hex = pkt_hex[14:22]
        if len(data_hex) < 8: return
        weight_frag = data_hex[1:-1]
        
        if weight_frag == '000000':
            weight = 0.0
        else:
            kg = int(weight_frag, 16) / 16000.0
            weight = round(kg, 2)

        # Improved logic for counting stable packets
        counter = 0
        if len(pakiety) > 1:
            current_stabil_frag = pkt_hex[4:]
            # Count how many times the same stabilization fragment occurs at the end of the list
            for p in reversed(pakiety):
                p_hex = p.replace(' ', '').lower()
                if len(p_hex) >= 22 and p_hex[4:] == current_stabil_frag:
                    counter += 1
                else:
                    break # Stop when a different packet is found
        else:
            counter = 1
            
        is_stable = counter >= min_stable
            
        if on_update:
            on_update(weight, counter, is_stable) # Added returning stability status
    except Exception as e:
        loguj(f"Weight decoding error: {e}", dopisek="ERROR")
        # Helper function to get ini path from default location or argument
        def get_ini_path(ini_path=None):
            """Returns the path to the ini file, default 'config/waga.ini'."""
            if ini_path and os.path.exists(ini_path):
                return ini_path
            default = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'waga.ini')
            return os.path.abspath(default)

def dekoduj_ffb3(hex_packet):
    """Decodes FFB3 packet with body analysis data from FiToGar scale"""
    try:
        if not hex_packet or len(hex_packet) < 70:
            print(f"Error: Packet too short: {len(hex_packet) if hex_packet else 0} characters")
            return None
        
        # Log received packet for diagnostics
        print(f"Decoding packet: {hex_packet}")
        
        # Improved helper function for little-endian conversion
        def extract_value(pos, length=4, divide_by=10.0):
            if pos + length > len(hex_packet):
                return 0
            value_hex = hex_packet[pos:pos+length]
            if len(value_hex) != length:
                return 0
                
            # Correction - big-endian format for 16-bit numbers
            if length == 4:
                value = int(value_hex, 16)
            else:
                value = int(value_hex, 16)
                
            return value / divide_by
        
        # Corrected positions in the packet
        # Example packet: 19002600a768637ace256d7aa2000a00690b360b0506cd079800420a0309d4064006e91212f35b0100d002
        
        # Extract values from the packet (after position correction)
        fat_perc = round(extract_value(36, 2, 1.0), 1)    # Fat %
        water_perc = round(extract_value(38, 2, 1.0), 1)  # Water %
        muscle_perc = round(extract_value(40, 2, 1.0), 1) # Muscle %
        bone_perc = round(extract_value(42, 2, 10.0), 1)  # Bone % - divided by 10
        bmi = round(extract_value(52, 2, 10.0), 1)        # BMI - divided by 10
        bmr = int(extract_value(48, 4, 1.0))              # BMR (kcal)
        
        # Additional values
        visceral_fat = int(extract_value(56, 2, 10.0))    # Visceral fat
        metabolic_age = int(extract_value(60, 2, 1.0))    # Metabolic age
        
        # Return dictionary with processed values
        return {
            'Fat %': fat_perc,
            'Water %': water_perc,
            'Muscle %': muscle_perc,
            'Bone %': bone_perc,
            'BMR (kcal)': bmr,
            'BMI': bmi,
            'Visceral fat': visceral_fat,
            'Metabolic age': metabolic_age
        }
    except Exception as e:
        print(f"FFB3 packet decoding error: {e}")
        import traceback
        traceback.print_exc()
        return None

def validate_ini_config(ini_path='config/waga.ini') -> bool:
    """Checks if the .ini config file contains required fields."""
    if not os.path.exists(ini_path):
        print(f"CRITICAL ERROR: Config file does not exist at '{ini_path}'")
        return False
        
    cfg = configparser.ConfigParser()
    cfg.read(ini_path, encoding='utf-8')
    errors = []
    required = {
        'PROGRAM': ['nazwa_pliku_log'],
        'GARMIN': ['garmin_email', 'tryb_wysylki'],
        'URZADZENIE': ['mac_address']
    }
    for section, fields in required.items():
        if not cfg.has_section(section):
            errors.append(f"Missing required section [{section}] in waga.ini")
            continue
        for field in fields:
            if not cfg.has_option(section, field) or not cfg.get(section, field).strip():
                errors.append(f"Missing or empty field '{field}' in section [{section}]")
    if errors:
        print("Errors in waga.ini config file:")
        for e in errors: print(f" - {e}")
        return False
        
    return True

def send_to_garmin_gc(waga: float, ini_path='config/waga.ini', ffb3_pkt=None) -> bool:
    """Sends data to Garmin Connect and returns operation status (True/False)."""
    cfg = configparser.ConfigParser()
    cfg.read(ini_path, encoding='utf-8')
    email = cfg.get("GARMIN", "garmin_email")
    password_hex = cfg.get("GARMIN", "garmin_password_hex", fallback=None)
    if not password_hex:
        loguj("Missing password (garmin_password_hex) in config file.", dopisek="error", ini_path=ini_path)
        return False
    password = bytes.fromhex(password_hex).decode("utf-8")
    ts = datetime.datetime.now().isoformat()
    try:        
        garmin = Garmin(email, password)
        garmin.login()
        garmin.add_body_composition(weight=waga, timestamp=ts)
        loguj(f"{waga:.2f} kg → Garmin Connect OK", dopisek="gc", ini_path=ini_path)
        return True
    except (GarminConnectAuthenticationError, GarminConnectTooManyRequestsError) as e:
        loguj(f"Garmin authentication ERROR: {e}", dopisek="error", ini_path=ini_path)
    except Exception as e:
        loguj(f"GC SEND ERROR: {e}", dopisek="error", ini_path=ini_path)
    return False

def send_to_garmin_api(weight: float, ini_path='config/waga.ini') -> bool:
    """Sends data to external API and returns operation status (True/False)."""
    cfg = configparser.ConfigParser()
    cfg.read(ini_path, encoding='utf-8')
    try:
        email = cfg.get('GARMIN', 'garmin_email')
        token = cfg.get('GARMIN', 'api_token')
        url = cfg.get('GARMIN', 'api_url')
    except Exception:
        return False
        
    headers = {'Authorization': f"Bearer {token}", 'Content-Type': 'application/json'}
    payload = {'email': email, 'timestamp': datetime.datetime.now().isoformat(), 'weight_kg': round(weight, 2)}
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        loguj(f"{weight:.2f} kg → API {resp.status_code}", dopisek="api", ini_path=ini_path)
        return True
    except Exception as e:
        loguj(f"API ERROR: {e}", dopisek="error", ini_path=ini_path)
    return False

def send_to_garmin(weight: float, ini_path='config/waga.ini', ffb3_pkt=None) -> bool:
    """MAIN ENTRY: automatic selection of GC or API. Returns True/False."""
    cfg = configparser.ConfigParser()
    cfg.read(ini_path, encoding='utf-8')
    mode = cfg.get('GARMIN', 'tryb_wysylki', fallback='gc').lower()
    
    if mode == 'gc':
        return send_to_garmin_gc(weight, ini_path=ini_path, ffb3_pkt=ffb3_pkt)
    elif mode == 'api':
        return send_to_garmin_api(weight, ini_path=ini_path)
    else:
        loguj(f"Unknown tryb_wysylki: {mode}", dopisek="error", ini_path=ini_path)
        return False
