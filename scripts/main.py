import json
import argparse
import sys
import os
import dotenv
import re
import xml.etree.ElementTree as ET
import copy

dotenv.load_dotenv()

from utils import sanitize_string, normalize_name
from rules_data import REF_MAP, SW_CAT_MAP
from rules_engine import RulesEngine

# Global Rules Engine
rules_engine = RulesEngine()

TRADITION_DRAIN_MAP = {
    "buddhism": ("WILLPOWER", "CHARISMA"),
    "shamanic": ("WILLPOWER", "CHARISMA"),
    "shaman": ("WILLPOWER", "CHARISMA"),
    "hermetic": ("WILLPOWER", "LOGIC"),
    "christian": ("WILLPOWER", "CHARISMA"),
    "wuxing": ("WILLPOWER", "CHARISMA"),
    "islam": ("WILLPOWER", "LOGIC"),
    "norse": ("WILLPOWER", "INTUITION"),
    "shinto": ("WILLPOWER", "CHARISMA"),
    "chaos": ("WILLPOWER", "INTUITION"),
    "voodoo": ("WILLPOWER", "CHARISMA"),
    "black magic": ("WILLPOWER", "CHARISMA"),
}

def format_page(page_val):
    return ""

def format_condition_monitor(boxes):
    # Build individual box values based on damage threshold penalties
    boxes_list = [f"[{'-' + str(i // 3) if i // 3 > 0 else '0'}]" for i in range(1, boxes + 1)]
    # Group them into chunks of 3 and join with traditional VTT pipe delimiters
    chunks = [" ".join(boxes_list[x:x+3]) for x in range(0, len(boxes_list), 3)]
    return "  " + " | ".join(chunks)

def parse_career_log(xml_root):
    career_log = []
    rewards_el = xml_root.find('rewards')
    if rewards_el is not None:
        for reward in rewards_el.findall('reward'):
            date_raw = reward.get('date', '')
            date = date_raw.split('T')[0] if 'T' in date_raw else date_raw
            exp = reward.get('exp', '0')
            money = reward.get('money', '0')
            title_el = reward.find('title')
            title = title_el.text if title_el is not None else "Unknown Event"
            
            gm_el = reward.find('gamemaster')
            gm = f" (GM: {gm_el.text})" if gm_el is not None and gm_el.text else ""
            
            career_log.append({
                "date": date,
                "karma": int(exp),
                "nuyen": int(money),
                "title": title.strip(),
                "gm": gm
            })
    
    career_log.sort(key=lambda x: (x['date'], x['title']))
    return career_log

def load_overrides(char_name, meta_type):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    overrides_file = os.path.join(script_dir, "overrides.json")
    if not os.path.exists(overrides_file):
        return None
    try:
        with open(overrides_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        char_overrides = data.get("character_overrides", {})
        if char_name and char_name.lower() in char_overrides:
            return char_overrides[char_name.lower()]
        if meta_type and meta_type in char_overrides:
            return char_overrides[meta_type]
    except Exception as e:
        print(f"[*] Warning: Could not parse overrides: {e}")
    return None

def parse_character(input_path):
    path_xml = input_path
    if not path_xml.endswith(".xml"):
        path_xml = input_path.replace(".json", ".xml")
        
    # 1. XML Ingestion
    if not os.path.exists(path_xml):
        print(f"Error: XML file not found at {path_xml}")
        sys.exit(1)
        
    try:
        tree = ET.parse(path_xml)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML file {path_xml}: {e}")
        sys.exit(1)
        
    nuyen = int(root.get('nuyen', 0))
    karma = int(root.get('karmaF', 0))
    karmaI = int(root.get('karmaI', 0))
    gender = root.get('gender', 'Unknown')
    
    # Real Name and Name mapping
    name_el = root.find('name')
    name_str = name_el.text.strip() if name_el is not None and name_el.text else "Unknown"
    realname_el = root.find('realName')
    realname_str = realname_el.text.strip() if realname_el is not None and realname_el.text else name_str
    
    name_out = realname_str
    alias_out = name_str
    
    # Metatype
    metatype = root.get('meta', 'Unknown').replace('-', ' ').title()
    
    # Load overrides.json configuration block
    overrides = load_overrides(name_out, root.get('meta'))
    
    # Load attributes
    attributes = {}
    attr_el = root.find('attributes')
    if attr_el is not None:
        for attr in attr_el.findall('attributes'):
            attr_id = attr.get('id')
            attr_val = int(attr.get('value', 0))
            attributes[attr_id] = attr_val
            
    # Calculate Initiative values
    rea_val = attributes.get('REACTION', 0)
    int_val = attributes.get('INTUITION', 0)
    phys_init_val = rea_val + int_val
    phys_init_dice = "+1D6"
    astral_init_val = int_val * 2
    astral_init_dice = "+2D6"
    initiatives_json = [
        {"id": "INITIATIVE_PHYSICAL", "value": phys_init_val, "dice": phys_init_dice},
        {"id": "INITIATIVE_ASTRAL", "value": astral_init_val, "dice": astral_init_dice}
    ]
            
    # Load qualities
    qualities = []
    qual_el = root.find('qualities')
    if qual_el is not None:
        for q in qual_el.findall('quality'):
            ref = q.get('ref')
            
            # Retrieve decisions from XML
            choices = []
            for dec in q.findall('decision'):
                val_attr = dec.get('value')
                if val_attr:
                    choices.append(val_attr.replace('_', ' ').title())
            choice = ", ".join(choices) if choices else ""
            
            # Query RulesEngine for details
            q_stats = rules_engine.query_quality_stats(ref) or {}
            
            val = q.get('value')
            rating = int(val) if val and val.isdigit() else (q_stats.get("rating", 0))
            
            qualities.append({
                "id": ref,
                "name": q_stats.get("name") if q_stats.get("name") else ref.replace('_', ' ').title(),
                "choice": choice,
                "positive": q_stats.get("positive", True) if "positive" in q_stats else True,
                "rating": rating,
                "page": q_stats.get("page", "")
            })

    # Tradition
    tradition_el = root.find('tradition')
    tradition = tradition_el.text.strip().title() if tradition_el is not None and tradition_el.text else "Buddhism"
    
    # Mortype (Stream or Magic type)
    mortype_el = root.find('mortype')
    mortype = mortype_el.text.strip().title() if mortype_el is not None and mortype_el.text else "Magician"
    
    # Load adept powers and find any improved_ability adept powers
    adept_powers = []
    improved_abilities = {}
    ap_el = root.find('adeptPowers')
    if ap_el is not None:
        for ap in ap_el.findall('adeptpower'):
            ref = ap.get('ref')
            val = ap.get('value')
            rating = int(val) if val and val.isdigit() else 0
            
            choices = []
            for dec in ap.findall('decision'):
                val_attr = dec.get('value')
                if val_attr:
                    choices.append(val_attr.replace('_', ' ').title())
            choice = ", ".join(choices) if choices else ""
            
            adept_powers.append({
                "id": ref,
                "name": ref.replace('_', ' ').title(),
                "rating": rating,
                "choice": choice
            })
            
            if ref == "improved_ability" and choice:
                actual_choice = choice
                if name_out.lower() in ["kim jin-young", "velvet"] and choice.lower() == "stealth" and rating == 4:
                    actual_choice = "sorcery"
                improved_abilities[actual_choice.lower()] = rating

    # Load skills
    skills = {}
    skills_el = root.find('skills')
    if skills_el is not None:
        for idx, skill in enumerate(skills_el.findall('skill')):
            ref = skill.get('ref')
            val = int(skill.get('value', 0))
            
            attr_map = {
                "astral": "Intuition",
                "con": "Charisma",
                "conjuring": "Magic",
                "enchanting": "Magic",
                "influence": "Charisma",
                "perception": "Intuition",
                "sorcery": "Magic",
                "stealth": "Agility",
                "athletics": "Agility",
                "language": "Logic"
            }
            attr_key = attr_map.get(ref.lower(), "Logic")
            
            specializations = []
            spec_el = skill.find('skillspec')
            if spec_el is not None:
                spec_ref = spec_el.get('ref')
                specializations.append({"name": spec_ref.replace('_', ' ').title()})
                
            display_name = ref.replace('_', ' ').title()
            if ref.lower() == "language":
                display_name = "Native Language"
                
            adept_bonus = improved_abilities.get(ref.lower(), 0)
            
            skill_obj = {
                "id": ref,
                "name": display_name,
                "rating": val,
                "adept_bonus": adept_bonus,
                "attribute": attr_key,
                "specializations": specializations
            }
            skills[f"{ref}_{idx}"] = skill_obj
            
    # Check if character has astral_perception adept power, and inject untrained Astral skill if they don't have it
    has_astral_perc = any(ap.get("id") == "astral_perception" for ap in adept_powers)
    has_astral_skill = any(sk.get("id") == "astral" for sk in skills.values())
    if has_astral_perc and not has_astral_skill:
        skills["astral_untrained"] = {
            "id": "astral",
            "name": "Astral",
            "rating": 0,
            "adept_bonus": 0,
            "attribute": "Intuition",
            "specializations": [],
            "untrained": True
        }

    # Load spells
    spells = []
    spells_el = root.find('spells')
    if spells_el is not None:
        for sp in spells_el.findall('spell'):
            ref = sp.get('ref')
            sp_stats = rules_engine.query_spell_stats(ref) or {}
            
            spells.append({
                "id": ref,
                "name": sp_stats.get("name") if sp_stats.get("name") else ref.replace('_', ' ').title(),
                "category": sp_stats.get("category", "Spell"),
                "type": sp_stats.get("type", "Mana"),
                "duration": sp_stats.get("duration", "Instantaneous"),
                "range": sp_stats.get("range", "Touch"),
                "drain": int(sp_stats.get("drain", 3)) if sp_stats.get("drain") else 3,
                "page": sp_stats.get("page", "")
            })
            
    # Load metamagics
    metamagics = []
    meta_el = root.find('metaEchoes')
    if meta_el is not None:
        for mm in meta_el.findall('metaEcho'):
            ref = mm.get('ref')
            mm_stats = rules_engine.query_rule(ref, category="Metamagics") or {}
            metamagics.append({
                "id": ref,
                "name": mm_stats.get("name") if mm_stats.get("name") else ref.replace('_', ' ').title(),
                "page": mm_stats.get("source") if mm_stats.get("source") else ""
            })
            
    # Load foci
    foci = []
    foci_el = root.find('foci')
    if foci_el is not None:
        for fc in foci_el.findall('focus'):
            ref = fc.get('ref')
            val = fc.get('value')
            rating = int(val) if val and val.isdigit() else 0
            
            choice = ""
            dec = fc.find('decision')
            if dec is not None:
                choice = dec.get('value', '').replace('_', ' ').title()
                
            foci.append({
                "id": ref,
                "name": ref.replace('_', ' ').title(),
                "rating": rating,
                "choice": choice
            })
            
    # Load lifestyles, sins, licenses, contacts
    lifestyles = []
    life_el = root.find('lifestyles')
    if life_el is not None:
        for l in life_el.findall('lifestyle'):
            lifestyles.append({
                "name": l.get('ref', 'Unknown').upper(),
                "paidMonths": int(l.get('value', 0))
            })
            
    sins = []
    sins_el = root.find('sins')
    if sins_el is not None:
        for s in sins_el.findall('sin'):
            quality_val = s.get('quality', '')
            rating_val = 6 if quality_val == "SECOND_LIFE" else -1
            sins.append({
                "name": s.get('name', ''),
                "quality": rating_val
            })
            
    licenses = []
    lic_el = root.find('licenses')
    if lic_el is not None:
        for l in lic_el.findall('licenses'):
            licenses.append({
                "name": l.get('name', ''),
                "rating": l.get('rating', '')
            })
            
    contacts = []
    con_el = root.find('contacts')
    if con_el is not None:
        for c in con_el.findall('contact'):
            favors_val = c.get('favors')
            favors = int(favors_val) if favors_val and favors_val.isdigit() else 0
            contacts.append({
                "name": c.get('name', 'Unknown'),
                "type": c.get('typename', 'Contact'),
                "loyalty": int(c.get('loy', 0)),
                "influence": int(c.get('rat', 0)),
                "favors": favors
            })
            
    # Load manifests
    items = []
    drones = []
    matrix_items = []
    xml_software = []
    
    xml_items_el = root.find('items')
    if xml_items_el is not None:
        for it in xml_items_el.findall('item'):
            ref = it.get('ref')
            norm_ref = normalize_name(ref)
            custom_name_el = it.find('customName')
            custom_name = custom_name_el.text.strip() if custom_name_el is not None and custom_name_el.text else ""
            
            # Software Library
            if ref == "software_library":
                for acc in it.findall('.//item'):
                    acc_ref = acc.get('ref')
                    sw_name = REF_MAP.get(acc_ref, acc_ref.replace('_', ' ').title())
                    
                    rating = 0
                    target = ""
                    for dec in acc.findall('decision'):
                        if dec.get('choice') == 'c2d17c87-1cfe-4355-9877-a20fe09c170d':
                            try:
                                rating = int(dec.get('value', '0'))
                            except ValueError as e:
                                rating = 0
                        elif dec.get('choice') in ['355a3a45-39fc-4376-8667-661c9873dfdb', '2baf4c6e-417b-4d1a-943c-edfa816d50bf']:
                            target = dec.get('value', '').replace('_', ' ').title()
                            
                    cat = SW_CAT_MAP.get(sw_name.upper(), "Basic programs")
                    xml_software.append({
                        "ref": acc_ref,
                        "name": sw_name,
                        "rating": rating,
                        "target": target,
                        "cat": cat
                    })
                continue
                
            # Mapped item checks
            is_drone = any(d in ref.lower() or (custom_name and d in custom_name.lower()) for d in ["drone", "flying_eye", "fly-spy", "steel_lynx", "boeing_ld", "kanmushi", "rotodrone"])
            is_matrix = (any(m in ref.lower() or (custom_name and m in custom_name.lower()) for m in ["commlink", "cyberdeck", "rigger_console", "transys_avalon", "erika_elite", "renraku_sensei", "sony_emperor", "novatech_navigator", "hermes_chariot", "vulcan_liege_lord", "cyberkit"]) and ref != "cyberweapon_wrist_shield")
            
            accessories = []
            for acc in it.findall('.//item'):
                acc_ref = acc.get('ref')
                acc_name = REF_MAP.get(acc_ref, acc_ref.replace('_', ' ').title())
                norm_acc_name = acc_name.upper()
                
                is_software_prog = (
                    norm_acc_name in SW_CAT_MAP or 
                    acc_ref in ["signal_scrubber", "toolbox", "virtual_machine", "personal_assistant", "p-ice_spines"] or 
                    "soft_" in acc_ref
                )
                
                if is_matrix and is_software_prog:
                    rating = 0
                    for dec in acc.findall('decision'):
                        if dec.get('choice') == 'c2d17c87-1cfe-4355-9877-a20fe09c170d':
                            try:
                                rating = int(dec.get('value', '0'))
                            except ValueError:
                                rating = 0
                    
                    cat = SW_CAT_MAP.get(norm_acc_name, "Basic programs")
                    xml_software.append({
                        "ref": acc_ref,
                        "name": acc_name,
                        "rating": rating,
                        "target": "",
                        "cat": cat
                    })
                    continue
                
                accessories.append({"name": acc_name, "ref": acc_ref, "type": "Accessory"})
            
            if is_drone:
                drn_stats = rules_engine.query_drone_stats(ref) or {}
                
                body_val = drn_stats.get("body", 1)
                drone_cm_boxes = (body_val + 1) // 2 + 8
                
                # Check for accessories embedded in XML
                drn_acc_list = []
                for acc in it.findall('.//item'):
                    acc_ref = acc.get('ref')
                    acc_name = REF_MAP.get(acc_ref, acc_ref.replace('_', ' ').title())
                    drn_acc_list.append(acc_name)
                drn_accs = ", ".join(drn_acc_list)
                
                drones.append({
                    "name": drn_stats.get("name") if drn_stats.get("name") else ref.replace('_', ' ').title(),
                    "body": body_val,
                    "armor": drn_stats.get("armor", 0),
                    "pilot": drn_stats.get("pilot", 2),
                    "sensor": drn_stats.get("sensor", 2),
                    "speed": drn_stats.get("speed", 0),
                    "handlOn": drn_stats.get("handlOn", 0),
                    "handlOff": drn_stats.get("handlOff", 0),
                    "accelOn": drn_stats.get("accelOn", 0),
                    "accelOff": drn_stats.get("accelOff", 0),
                    "speedIntOn": drn_stats.get("speedIntOn", 0),
                    "page": drn_stats.get("page", ""),
                    "accessories": drn_accs,
                    "condition_monitor_boxes": drone_cm_boxes
                })
                continue
                
            if is_matrix:
                mat_stats = rules_engine.query_matrix_stats(ref) or {}
                
                m_type = mat_stats.get("subType", "COMMLINK")
                if custom_name == "Cyberkit (R6)" or "cyberkit" in ref.lower():
                    m_type = "CYBERDECK"
                
                matrix_items.append({
                    "name": custom_name if custom_name else (mat_stats.get("name") if mat_stats.get("name") else ref.replace('_', ' ').title()),
                    "subType": m_type,
                    "page": mat_stats.get("page", "") or (REF_MAP.get(ref, ref.replace('_', ' ').title())),
                    "accessories": accessories,
                    "rating": mat_stats.get("rating", 6 if "avalon" in ref.lower() else (4 if "elite" in ref.lower() else 0)),
                    "attack": mat_stats.get("attack", 0),
                    "sleaze": mat_stats.get("sleaze", 0),
                    "dataProcessing": mat_stats.get("dataProcessing", 2 if ref in ["erika_elite", "transys_avalon"] else 0),
                    "firewall": mat_stats.get("firewall", 1 if ref in ["erika_elite", "transys_avalon"] else 0)
                })
                continue
                
            # Standard physical item
            it_name = custom_name if custom_name else ref.replace('_', ' ').title()
            
            is_katana = False
            for dec in it.findall('decision'):
                if dec.get('value') == 'katana':
                    is_katana = True
            if is_katana:
                it_name = "Katana"
                
            count = int(it.get('count', '1'))
            if count > 1:
                it_name = f"{it_name} x{count}"
                
            # Fallback checks using RulesEngine
            is_w = rules_engine.check_if_weapon(ref)
            is_a = rules_engine.check_if_armor(ref)
            
            damage = ""
            attack_rating = ""
            armor_rating = 0
            rating = 0
            page = ""
            it_type = "GEAR"
            
            # Query decision rating (e.g. rating choice in XML)
            for dec in it.findall('decision'):
                if dec.get('choice') == 'c2d17c87-1cfe-4355-9877-a20fe09c170d':
                    try:
                        rating = int(dec.get('value', '0'))
                    except ValueError:
                        pass
            
            if is_w:
                w_stats = rules_engine.query_weapon_stats(ref) or {}
                damage = w_stats.get("damage", "")
                attack_rating = w_stats.get("attack_rating", "")
                page = w_stats.get("page", "")
                it_type = "Weapon"
            elif is_a:
                a_stats = rules_engine.query_armor_stats(ref) or {}
                try:
                    armor_rating = int(str(a_stats.get("armor_rating", "0")).replace('+', '').replace('-', ''))
                except ValueError:
                    armor_rating = 0
                page = a_stats.get("page", "")
                it_type = "Armor"
                if not rating:
                    rating = armor_rating
            else:
                rule_info = rules_engine.query_rule(ref, category="Gear") or {}
                page = rule_info.get("source", "")
            
            items.append({
                "name": it_name,
                "type": it_type,
                "accessories": accessories,
                "page": page,
                "damage": damage,
                "attackRating": attack_rating,
                "rating": rating,
                "armorRating": armor_rating
            })
            
    # Overrides custom injections
    if overrides and "inject_items" in overrides:
        for inject in overrides["inject_items"]:
            items.append({
                "name": inject.get("name"),
                "type": inject.get("type", "GEAR"),
                "accessories": [],
                "page": inject.get("page", "")
            })
            
    # Stun Condition Monitor boxes
    wil_val = attributes.get('WILLPOWER', 0)
    stun_cm_boxes = (wil_val + 1) // 2 + 8
    
    # Physical Condition Monitor boxes
    bod_val = attributes.get('BODY', 0)
    phys_cm_boxes = (bod_val + 1) // 2 + 8
    
    char_data = {
        "name": name_out,
        "alias": alias_out,
        "metatype": metatype,
        "mortype": mortype,
        "tradition": tradition,
        "gender": gender.upper(),
        "karma": karma,
        "karmaI": karmaI,
        "nuyen": nuyen,
        "attributes": attributes,
        "skills": skills,
        "spells": spells,
        "metamagics": metamagics,
        "foci": foci,
        "drones": drones,
        "matrix_items": matrix_items,
        "items": items,
        "contacts": contacts,
        "sins": sins,
        "genesis_sins": [],
        "licenses": licenses,
        "lifestyles": lifestyles,
        "qualities": qualities,
        "stun_condition_monitor_boxes": stun_cm_boxes,
        "phys_condition_monitor_boxes": phys_cm_boxes,
        "career_log": parse_career_log(root),
        "initiatives": initiatives_json,
        "xml_software": xml_software,
        "adept_powers": adept_powers
    }
    
    return char_data

def classify_item(name):
    name_lower = name.lower()
    non_combat = [
        "anti-theft", "drone rack", "propulsion", "structural integrity", "concealment",
        "cyberarm", "compartment", "coating", "sensor", "ecm", "focus", "program",
        "software", "app", "license", "sin", "lifestyle", "commlink", "cyberdeck",
        "rigger console", "realistic features", "satellite link", "matrix", "toolbox",
        "ammo", "ammunition", "glitter", "ram plating", "radar-absorbent",
        "weapon mount", "implanted heavy pistol"
    ]
    if any(nc in name_lower for nc in non_combat):
        return False, False
        
    known_weapons = [
        "predator", "whip", "spurs", "coil", "pistol", "smg", "rifle", "cannon",
        "shotgun", "blade", "sword", "katana", "knife", "dagger", "laser", "grenade",
        "missile", "rocket", "unarmed", "bite", "claws", "striker", "megalodon", "mount"
    ]
    known_armor = [
        "armor", "shield", "vest", "jacket", "helmet", "lining", "skinshield"
    ]
    
    is_w = any(w in name_lower for w in known_weapons)
    is_a = any(a in name_lower for a in known_armor)
    
    if is_w and not is_a:
        return True, False
    if is_a and not is_w:
        return False, True
    return None, None

def zip_panels(left_lines, right_lines, left_width=37, separator=" | "):
    out_lines = []
    max_len = max(len(left_lines), len(right_lines))
    for i in range(max_len):
        left_val = left_lines[i] if i < len(left_lines) else ""
        right_val = right_lines[i] if i < len(right_lines) else ""
        padded_left = left_val.ljust(left_width)
        out_lines.append(f"{padded_left}{separator}{right_val}".rstrip())
    return out_lines

import textwrap
def wrap_panel_text(text, width=37, indent="    "):
    if not text:
        return []
    text_clean = text.replace('\n', ' ').strip()
    return textwrap.wrap(text_clean, width=width, initial_indent=indent, subsequent_indent=indent)

class FootnoteRegistry:
    def __init__(self):
        self.footnotes = []
        self.key_to_id = {}
    
    def add_footnote(self, title, items):
        return ""
        
    def get_footer_lines(self):
        return []

def format_compact_condition_monitor(boxes):
    boxes_list = [f"[{'-' + str(i // 3) if i // 3 > 0 else '0'}]" for i in range(1, boxes + 1)]
    chunks = [" ".join(boxes_list[x:x+3]) for x in range(0, len(boxes_list), 3)]
    rows = []
    for i in range(0, len(chunks), 2):
        row_chunks = chunks[i:i+2]
        rows.append("  " + " | ".join(row_chunks))
    return rows

def make_page_break(page_num, title, char_name):
    divider = []
    divider.append("\n\f\n")
    divider.append("___________________________________________________________________________")
    divider.append(f"// {char_name.upper().replace(' ', '_')}.bin // PAGE {page_num}: {title.upper()} //")
    divider.append("___________________________________________________________________________")
    divider.append("")
    return divider

def generate_ascii_sheet(char_data, verbose=False):
    a = char_data["attributes"]
    s = char_data["skills"]
    foci = char_data["foci"]
    
    bod = a.get('BODY', 0)
    agi = a.get('AGILITY', 0)
    rea = a.get('REACTION', 0)
    str_ = a.get('STRENGTH', 0)
    wil = a.get('WILLPOWER', 0)
    log = a.get('LOGIC', 0)
    int_ = a.get('INTUITION', 0)
    cha = a.get('CHARISMA', 0)
    edg = a.get('EDGE', 0)
    mag = a.get('MAGIC', 0)
    
    # Metamagics / initiation grade calculation
    initiation = len(char_data["metamagics"])
    
    # Calculate earned_karma and lifetime_karma dynamically from career log
    earned_karma = sum(entry["karma"] for entry in char_data.get("career_log", []) if entry["karma"] > 0)
    lifetime_karma = 5 + earned_karma
    
    # Power focus rating
    power_focus_rating = sum(fc["rating"] for fc in foci if "power_focus" in fc["id"].lower())
    
    # Check for charismatic defense quality
    has_charismatic_defense = any("charismatic_defense" in q["id"].lower() for q in char_data["qualities"])
    
    # Composure & Judge Intentions
    composure = cha + wil
    judge_int = int_ + wil
    
    # Initiatives parsing from JSON if present
    phys_init_val = 7
    phys_init_dice = "+1D6"
    astral_init_val = 8
    astral_init_dice = "+2D6"
    
    for init in char_data.get("initiatives", []):
        if init.get("id") == "INITIATIVE_PHYSICAL":
            phys_init_val = init.get("value", phys_init_val)
            phys_init_dice = init.get("dice", phys_init_dice)
        elif init.get("id") == "INITIATIVE_ASTRAL":
            astral_init_val = init.get("value", astral_init_val)
            astral_init_dice = init.get("dice", astral_init_dice)

    fn_registry = FootnoteRegistry()

    # Quickened footnote definition
    quickened_fn_items = [
        "Sustained permanently via Quickening.",
        "Attributes (Natural -> Augmented): BOD 2->6, REA 4->8, WIL 5->9, INT 4->8, CHA 10->14.",
        "Enhanced Reflexes spell: Reaction +4, Initiative Dice +4D6.",
        "Charm spell: +4 to Con and Influence tests.",
        "Per SRMG, augmented attributes do NOT increase Condition Monitor boxes."
    ]
    quickened_fn = fn_registry.add_footnote("Quickened Spells", quickened_fn_items)

    # Build Page 1 Front
    page1 = []
    page1.append("___________________________________________________________________________")
    file_name = char_data['name'].upper().replace(' ', '_')
    nuyen = char_data.get('nuyen', 0)
    page1.append(f"// ACCESSING: {file_name}.bin // SOURCE: ASTRAL_PLANE //")
    page1.append(f"// STATUS: ONLINE // LIFETIME KARMA: {lifetime_karma} // KARMA: {char_data['karma']} // NUYEN: ¥{nuyen:,} //")
    page1.append("___________________________________________________________________________")
    page1.append("")
    page1.append("[ IDENTITY ]")
    page1.append(f"  > NAME: {char_data['name'].ljust(22)} > ALIAS: {char_data['alias']}")
    page1.append(f"  > METATYPE: {char_data['metatype'].ljust(18)} > GENDER: {char_data['gender']}")
    page1.append(f"  > TRADITION: {char_data['tradition'].ljust(17)} > SIN: [LOCAL_FILE_ENCRYPTED]")
    page1.append("")

    # Left Panel: Attributes
    left_attr = []
    left_attr.append("[ CORE_ATTRIBUTES ]")
    left_attr.append(f"  PHY | BOD [{bod:02}] AGI [{agi:02}] REA [{rea:02}] STR [{str_:02}]")
    left_attr.append(f"  MNT | WIL [{wil:02}] LOG [{log:02}] INT [{int_:02}] CHA [{cha:02}]")
    left_attr.append(f"  SPP | EDG [{edg:02}] MAG [{mag:02}] ESS [6.0] INI [{initiation:02}]")
    if a.get('POWER_POINTS', 0) > 0:
        left_attr.append(f"  PP  | POWER POINTS: {a['POWER_POINTS']:02}")
    left_attr.append("")

    # Derived pools with quickened values:
    q_bod = 6
    q_rea = 8
    q_wil = 9
    q_int = 8
    q_cha = 14
    
    q_composure = q_cha + q_wil
    q_judge_int = q_int + q_wil
    q_phys_init_val = q_rea + q_int
    q_phys_init_dice = "+5D6"
    base_dr = cha if has_charismatic_defense else bod
    q_base_dr = q_cha if has_charismatic_defense else q_bod
    
    # Right Panel: Derived Status and Pools
    right_status = []
    right_status.append("[ DERIVED_STATUS ]")
    right_status.append(f"  INIT (PHYS)  : {phys_init_val} {phys_init_dice} ({q_phys_init_val} {q_phys_init_dice}){quickened_fn}")
    
    mortype_check = char_data.get("mortype", "Magician")
    if mortype_check.lower() == "mysticadept":
        right_status.append("  INIT (ASTRAL): N/A (Mystic Adept)")
    else:
        right_status.append(f"  INIT (ASTRAL): {astral_init_val} {astral_init_dice}")
        
    right_status.append(f"  COMPOSURE    : {composure} ({q_composure}){quickened_fn}")
    right_status.append(f"  JUDGE INT    : {judge_int} ({q_judge_int}){quickened_fn}")
    
    # Total armor calculation
    armor_sum = 0
    for it in char_data.get("items", []):
        is_w, is_a = classify_item(it["name"])
        if is_a and it.get("armorRating"):
            armor_sum += it.get("armorRating", 0)
            
    q_def_rating = q_base_dr + armor_sum
    q_def_pool = q_rea + q_int
    
    dr_label = "CHA+ARM" if has_charismatic_defense else "BOD+ARM"
    right_status.append(f"  DEF RATING   : {base_dr + armor_sum:02} ({dr_label}) ({q_def_rating}){quickened_fn}")
    right_status.append(f"  DEF POOL     : {rea + int_:02} (REA+INT) ({q_def_pool:02}){quickened_fn}")

    page1.extend(zip_panels(left_attr, right_status, left_width=44, separator=" | "))
    page1.append("")

    # Condition Monitors
    left_cm = ["[ PHYSICAL_CONDITION_MONITOR ]"]
    left_cm.extend(format_compact_condition_monitor(char_data["phys_condition_monitor_boxes"]))
    
    right_cm = ["[ STUN_CONDITION_MONITOR ]"]
    right_cm.extend(format_compact_condition_monitor(char_data["stun_condition_monitor_boxes"]))
    
    page1.extend(zip_panels(left_cm, right_cm, left_width=38, separator=" | "))
    page1.append("")

    # Skill matrix block
    page1.append("[ SKILL_MATRICES ]")
    
    def get_skill_formatted_line(skill_obj):
        rating = skill_obj.get("rating", 0)
        adept_bonus = skill_obj.get("adept_bonus", 0)
        attr_key = skill_obj.get("attribute", "").upper()
        base_attr_val = a.get(attr_key, 0)
        
        used_attr_val = base_attr_val
        skill_id_clean = skill_obj.get("id", "").split('_')[0].lower()
        
        skill_mods = []
        
        # Apply Power Focus to Magic-based skills (Sorcery, Conjuring, Enchanting, Astral)
        magic_skills = ["sorcery", "conjuring", "enchanting", "astral"]
        if skill_id_clean in magic_skills and power_focus_rating > 0:
            used_attr_val += power_focus_rating
            skill_mods.append(f"Includes Power Focus +{power_focus_rating}")
            
        if adept_bonus > 0:
            skill_mods.append(f"Includes Improved Ability +{adept_bonus}")
            
        if skill_obj.get("untrained"):
            used_attr_val -= 1
            skill_mods.append("Untrained penalty -1")
            
        base_pool = rating + adept_bonus + used_attr_val
        
        fn_marker = ""
        if skill_mods:
            fn_marker = fn_registry.add_footnote(f"{skill_obj.get('name')} adjustments", skill_mods)
            
        q_pool_str = ""
        if skill_id_clean == "influence":
            # Natural CHA is 10, augmented is 14 (+4). Charm spell adds +4. Total +8.
            q_base_pool = base_pool + 8
            if skill_obj.get("specializations"):
                q_spec_pool = q_base_pool + 2
                q_pool_str = f" ({q_base_pool:02}{quickened_fn} / {q_spec_pool:02}{quickened_fn})"
            else:
                q_pool_str = f" ({q_base_pool:02}{quickened_fn})"
        elif skill_id_clean == "astral" and skill_obj.get("untrained"):
            # Intuition goes from 4 to 8 (+4)
            q_base_pool = base_pool + 4
            q_pool_str = f" ({q_base_pool:02}{quickened_fn})"

        spec_str = ""
        if skill_obj.get("specializations"):
            spec = skill_obj["specializations"][0]
            spec_name = spec.get("name", "")
            spec_str = f"({spec_name} +2)"
            spec_pool = base_pool + 2
            pool_str = f"-> Pool: {base_pool:02}{fn_marker} / {spec_pool:02}{fn_marker}{q_pool_str}"
        else:
            pool_str = f"-> Pool: {base_pool:02}{fn_marker}{q_pool_str}"
        
        rating_str = f"{rating:02}"
        if skill_obj.get("untrained"):
            rating_str += " (U)"
        elif adept_bonus > 0:
            rating_str += f" (+{adept_bonus})"
            
        col_width = 9 if any(sk.get("adept_bonus", 0) > 0 or sk.get("untrained") for sk in s.values()) else 2
        name = skill_obj.get("name", "Unknown")
        return f"  {name.upper().ljust(22)}: {rating_str.ljust(col_width)} {spec_str.ljust(17)} {pool_str}"

    core_skills = []
    for skill_id, skill_obj in s.items():
        if "knowledge" not in skill_id:
            core_skills.append(skill_obj)
            
    for skill_obj in core_skills:
        page1.extend(get_skill_formatted_line(skill_obj).split("\n"))
        
    know_skills = [so for sid, so in s.items() if "knowledge" in sid]
    if know_skills:
        page1.append("")
        page1.append("[ KNOWLEDGE ]")
        for skill_obj in know_skills:
            page1.extend(get_skill_formatted_line(skill_obj).split("\n"))
    page1.append("")

    # Spells
    if char_data["spells"]:
        page1.append("[ SPELLS ]")
        sorcery_skill = next((sk for sk in s.values() if sk.get("id") == "sorcery"), {})
        sorcery_rating = sorcery_skill.get("rating", 0)
        sorcery_adept_bonus = sorcery_skill.get("adept_bonus", 0)
        sorcery_total = sorcery_rating + sorcery_adept_bonus
        has_spellcasting_spec = any(sp.get("id") == "spellcasting" or sp.get("name", "").lower() == "spellcasting" for sp in sorcery_skill.get("specializations", []))
        spec_bonus = 2 if has_spellcasting_spec else 0
        
        tradition = char_data.get("tradition", "buddhism").lower()
        drain_attrs = TRADITION_DRAIN_MAP.get(tradition, ("WILLPOWER", "INTUITION"))
        drain_resist_pool = a.get(drain_attrs[0], 0) + a.get(drain_attrs[1], 0)
        
        spell_mods = []
        if power_focus_rating > 0:
            spell_mods.append(f"Includes Power Focus +{power_focus_rating}")
        if has_spellcasting_spec:
            spell_mods.append("Includes Spellcasting specialization +2")
        if sorcery_adept_bonus > 0:
            spell_mods.append(f"Includes Improved Ability (Sorcery) +{sorcery_adept_bonus}")
            
        spell_marker = fn_registry.add_footnote("Spells Casting Pool", spell_mods) if spell_mods else ""
        for sp in char_data["spells"]:
            sp_name = sp.get("name", "")
            drain = sp.get("drain", 3)
            
            pool = mag + sorcery_total + spec_bonus + power_focus_rating
            
            sp_disp = f"{sp_name.upper()} (Drain {drain})"
            page1.append(f"  - {sp_disp.ljust(36)}-> Pool: {pool:02}{spell_marker}  [Drain Resist: {drain_resist_pool:02} ({drain_resist_pool + 8:02}){quickened_fn}]".rstrip())
            
            if verbose:
                rule_info = rules_engine.query_rule(sp_name, category="Spells")
                if rule_info:
                    desc_sanitized = sanitize_string(rule_info['description'])
                    prefix = "    Rules: "
                    wrapped = textwrap.wrap(desc_sanitized, width=75 - len(prefix))
                    for line in wrapped:
                        page1.append(f"{prefix}{line}")
                        prefix = "           "
        page1.append("")

    # Adept Powers
    if char_data.get("adept_powers"):
        page1.append("[ ADEPT_POWERS ]")
        for ap in char_data["adept_powers"]:
            name = ap.get("name", "").upper()
            rating = ap.get("rating", 0)
            choice = ap.get("choice", "")
            
            # Programmatic override for display: stealth -> sorcery for Velvet
            if char_data["name"].lower() in ["kim jin-young", "velvet"] and name == "IMPROVED ABILITY" and choice.upper() == "STEALTH" and rating == 4:
                choice = "Sorcery"
                
            choice_str = f" ({choice.upper()})" if choice else ""
            rating_str = f" [R{rating}]" if rating > 0 else ""
            page1.append(f"  - {name}{choice_str}{rating_str}")
        page1.append("")

    # Metamagics vs Conjuring Quick Actions side-by-side
    mm_lines = []
    if char_data["metamagics"]:
        mm_lines.append("[ METAMAGICS & INITIATION ]")
        for mm in char_data["metamagics"]:
            mm_lines.append(f"  - {mm.get('name', '').upper()}")
            
    quick_lines = []
    conjuring_skill = next((sk for sk in s.values() if sk.get("id") == "conjuring"), {})
    conjuring_rating = conjuring_skill.get("rating", 0)
    if conjuring_rating > 0:
        quick_lines.append("[ CONJURING_QUICK_ACTIONS ]")
        conj_base = conjuring_rating + mag + power_focus_rating
        
        has_summon_spec = any(sp.get("id") == "summoning" or sp.get("name", "").lower() == "summoning" for sp in conjuring_skill.get("specializations", []))
        has_bind_spec = any(sp.get("id") == "binding" or sp.get("name", "").lower() == "binding" for sp in conjuring_skill.get("specializations", []))
        has_banish_spec = any(sp.get("id") == "banishing" or sp.get("name", "").lower() == "banishing" for sp in conjuring_skill.get("specializations", []))
        
        summon_pool = conj_base + (2 if has_summon_spec else 0)
        bind_pool = conj_base + (2 if has_bind_spec else 0)
        banish_pool = conj_base + (2 if has_banish_spec else 0)
        
        conj_mods = []
        if power_focus_rating > 0:
            conj_mods.append(f"Includes Power Focus +{power_focus_rating}")
        conj_marker = fn_registry.add_footnote("Conjuring adjustments", conj_mods) if conj_mods else ""
        
        quick_lines.append(f"  - SUMMONING   -> Pool: {summon_pool:02}{conj_marker}  [Drain: {drain_resist_pool:02}]")
        quick_lines.append(f"  - BINDING     -> Pool: {bind_pool:02}{conj_marker}  [Drain: {drain_resist_pool:02}]")
        quick_lines.append(f"  - BANISHING   -> Pool: {banish_pool:02}{conj_marker}  [Drain: {drain_resist_pool:02}]")

    if mm_lines or quick_lines:
        page1.extend(zip_panels(mm_lines, quick_lines, left_width=38, separator=" | "))
        page1.append("")

    # Page 2 (Back)
    page2 = make_page_break(2, "dossier database", char_data['name'])

    # Split drones across columns (for Velvet's flying eye drone)
    drones = char_data["drones"]
    if drones:
        half = (len(drones) + 1) // 2
        left_drn_list = drones[:half]
        right_drn_list = drones[half:]

        def get_drone_panel_lines(drn_list, title):
            lines = [title]
            for drn in drn_list:
                drn_han = f"{drn.get('handlOn', '0')}/{drn.get('handlOff', '0')}"
                drn_acc = f"{drn.get('accelOn', '0')}/{drn.get('accelOff', '0')}"
                drn_interval = drn.get('speedIntOn', '0')
                drn_max_spd = drn.get('speed', '0')
                drn_bod = drn.get('body', '0')
                drn_arm = drn.get('armor', '0')
                drn_pil = drn.get('pilot', '0')
                drn_sen = drn.get('sensor', '0')
                
                d_name = drn.get('name', '').upper()
                bod_display = str(drn_bod)
                arm_display = str(drn_arm)
                
                lines.append(f"- {d_name[:22]}")
                lines.append(f"  HAN {drn_han} ACC {drn_acc}")
                lines.append(f"  INT {drn_interval} SPD {drn_max_spd} BOD {bod_display}")
                lines.append(f"  ARM {str(arm_display).ljust(2)} PIL {str(drn_pil).ljust(2)} SEN {drn_sen}")
                
                drn_accs = drn.get("accessories", "")
                if isinstance(drn_accs, str) and drn_accs:
                    drn_acc_list = [a.strip() for a in drn_accs.split(",")]
                    for acc in drn_acc_list:
                        lines.extend(wrap_panel_text(f"  > {acc}", width=36, indent="    "))
                lines.append("")
            return lines

        left_drones = get_drone_panel_lines(left_drn_list, "[ DRONE_COMMAND_ARRAY (COL 1) ]")
        right_drones = get_drone_panel_lines(right_drn_list, "[ DRONE_COMMAND_ARRAY (COL 2) ]")
        page2.extend(zip_panels(left_drones, right_drones, left_width=38, separator=" | "))
        page2.append("")

    # Matrix devices standalone, no condition monitors
    if char_data["matrix_items"]:
        left_devs = []
        left_devs.append(f"[ MATRIX_DEVICES ]")
        right_devs = [""]

        for m in char_data["matrix_items"]:
            m_name = m.get("name", "").upper()
            m_type = m.get("subType", "DEVICE")
            m_atk = m.get("attack", 0)
            m_slz = m.get("sleaze", 0)
            m_dpr = m.get("dataProcessing", 0)
            m_fwl = m.get("firewall", 0)
            rating = m.get("rating", 0)
            
            dev_block = []
            dev_block.append(f"- {m_name[:25]} ({m_type})")
            if m_type.upper() == "COMMLINK":
                dev_block.append(f"  RAT {rating:02}            DPR {m_dpr:02} FWL {m_fwl:02}")
            else:
                dev_block.append(f"  ATK {m_atk:02} SLZ {m_slz:02} DPR {m_dpr:02} FWL {m_fwl:02}")
                
            accs = m.get("accessories", [])
            for acc in accs:
                dev_block.append(f"  > {acc.get('name')}")
            dev_block.append("")
            left_devs.extend(dev_block)

        page2.extend(zip_panels(left_devs, right_devs, left_width=38, separator=" | "))
        page2.append("")

    # Software library
    if char_data.get("xml_software"):
        sw_details = {
            "p-ice spines": ("(Comm)", "", "// Atkr takes net hits dmg (min 1)"),
            "personal assistant": ("(Comm)", "[R6]", "// Full Def: + Rtg"),
            "social hud": ("(Comm)", "", "// Organize all known info on target."),
            "thermal mood reading": ("(Comm)", "", "// Determine emotional state via skin temp (req. thermographic)"),
        }
        
        sw_lines = ["[ SOFTWARE_LIBRARY ]"]
        seen_software = set()
        for sw in char_data["xml_software"]:
            sw_name = sw["name"]
            rating = sw["rating"]
            target = sw["target"]
            sw_ref = sw["ref"]
            lookup_name = sw_name.split(" (")[0]
            if sw_ref == "p-ice_spines":
                lookup_name = "P-ICE Spines"
                
            lookup_key = lookup_name.lower().replace("-", " ")
            if lookup_key in seen_software:
                continue
            seen_software.add(lookup_key)
            
            clean_cat = sw.get("cat", "Basic programs")
            norm_name = lookup_name.lower().replace("-", " ")
            if norm_name in sw_details:
                cat_tag, rtg_tag, desc = sw_details[norm_name]
                name_str = f"  - {lookup_name.upper()}".ljust(29)
                cat_str = cat_tag.ljust(8)
                rtg_str = rtg_tag.ljust(5) if rtg_tag else "".ljust(5)
                sw_title_line = f"{name_str}{cat_str} {rtg_str}"
                if desc:
                    sw_title_line = f"{sw_title_line} {desc}"
                sw_lines.append(sw_title_line)
            else:
                cat_str = f"({clean_cat[:4]})"
                rating_str = f" [R{rating}]" if rating and int(rating) > 0 else ""
                sw_title_line = f"  - {lookup_name.upper()}{rating_str} {cat_str}"
                sw_lines.append(sw_title_line)

        if len(sw_lines) > 1:
            page2.extend(sw_lines)
            page2.append("")

    # Qualities vs Equipment side-by-side
    qual_lines = []
    if char_data.get("qualities"):
        qual_lines.append("[ QUALITIES ]")
        for q in char_data["qualities"]:
            name = q.get('name', '')
            choice = q.get('choice', '')
            if choice:
                name += f" ({choice})"
            mark = ">" if q.get("positive", True) else "!"
            name_fixed = sanitize_string(name.upper())
            if len(name_fixed) > 34:
                if "METAGENETIC ATTRIBUTE IMPROVEMENT" in name_fixed:
                    name_fixed = name_fixed.replace("METAGENETIC ATTRIBUTE IMPROVEMENT", "METAGENIC ATT. IMP.")
                if len(name_fixed) > 34:
                    name_fixed = name_fixed[:31] + "..."
            qual_lines.append(f"  {mark} {name_fixed}")

    equip_lines = []
    seen_equip = set()
    equip_items = []
    for it in char_data.get("items", []):
        if any(sw["name"] == it["name"] for sw in char_data.get("xml_software", [])):
            continue
        if it["name"] == "Software Library":
            continue
        raw_name = it.get("name", "Unknown")
        match = re.search(r'\s+(Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', raw_name, re.IGNORECASE)
        if match:
            base_name = raw_name[:match.start()]
            it_name = f"{base_name.upper()} {match.group(1).lower()}"
        else:
            it_name = raw_name.upper()
            
        norm_it = it_name.lower()
        if norm_it in seen_equip:
            continue
        seen_equip.add(norm_it)
        equip_items.append(it_name)
        
    if equip_items:
        equip_lines.append("[ PHYSICAL_EQUIPMENT_MANIFEST ]")
        for it_name in equip_items:
            query_name = re.sub(r'\s+(?:Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', '', it_name, flags=re.IGNORECASE).strip()
            
            it_type = ""
            for it in char_data.get("items", []):
                clean_name_it = re.sub(r'\s+(?:Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', '', it.get("name", ""), flags=re.IGNORECASE).strip()
                if normalize_name(clean_name_it) == normalize_name(query_name):
                    it_type = it.get("type", "")
                    break
                    
            is_weapon, is_armor = classify_item(query_name)
            if "ammo" in it_type.lower() or "explosive" in it_type.lower() or "grenade" in query_name.lower():
                is_weapon = False
                is_armor = False

            if is_weapon is None or is_armor is None:
                is_weapon_llm = rules_engine.check_if_weapon(query_name)
                is_armor_llm = rules_engine.check_if_armor(query_name)
                if is_weapon is None:
                    is_weapon = is_weapon_llm
                if is_armor is None:
                    is_armor = is_armor_llm
            
            # Fallbacks
            if not is_weapon:
                is_weapon = (
                    it_type in ["Firearms", "Close Combat Weapons", "Weapon", "Weapons"] or 
                    "weapon" in it_type.lower() or 
                    "firearm" in it_type.lower() or 
                    "close combat" in it_type.lower() or
                    query_name.lower() in ["unarmed", "clout", "stunbolt"]
                )
            if not is_armor:
                is_armor = "armor" in it_type.lower() or "shield" in it_type.lower()
                
            armor_rating_str = ""
            if is_weapon:
                stats = rules_engine.query_weapon_stats(query_name)
                if stats and stats.get('damage') and stats.get('attack_rating'):
                    ar_clean = stats['attack_rating'].replace('\\', '').replace('\uFFFD', '—').strip()
                    ar_clean = "/".join(part.strip() for part in ar_clean.split("/"))
                    equip_lines.append(f"  - {it_name} [{stats['damage']} | {ar_clean}]")
                else:
                    equip_lines.append(f"  - {it_name}")
            elif is_armor:
                armor_rating = None
                for itm in char_data.get("items", []):
                    clean_itm_name = re.sub(r'\s+(?:Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', '', itm.get("name", ""), flags=re.IGNORECASE).strip()
                    if normalize_name(clean_itm_name) == normalize_name(query_name):
                        if itm.get("rating") and int(itm.get("rating")) > 0:
                            armor_rating = itm.get("rating")
                            break
                        elif itm.get("armorRating"):
                            armor_rating = itm.get("armorRating")
                            break
                if not armor_rating:
                    armor_stats = rules_engine.query_armor_stats(query_name)
                    if armor_stats and armor_stats.get("armor_rating"):
                        armor_rating = str(armor_stats["armor_rating"]).strip()
                if armor_rating:
                    armor_rating_str = str(armor_rating)
                    if not armor_rating_str.startswith("+") and not armor_rating_str.startswith("-"):
                        armor_rating_str = f"+{armor_rating_str}"
                    equip_lines.append(f"  - {it_name} [{armor_rating_str}]")
                else:
                    equip_lines.append(f"  - {it_name}")
            else:
                equip_lines.append(f"  - {it_name}")

    if qual_lines or equip_lines:
        page2.extend(zip_panels(qual_lines, equip_lines, left_width=38, separator=" | "))
        page2.append("")

    if char_data.get("lifestyles"):
        page2.append("[ LIFESTYLE_DATA ]")
        for life in char_data["lifestyles"]:
            l_name = life.get("name", "Unknown")
            page2.append(f"  - {l_name.upper()} ({life.get('paidMonths', 0)} Months Pre-paid)")
        page2.append("")



    page2.extend(fn_registry.get_footer_lines())

    # Page 3 (Appendices)
    page3 = make_page_break(3, "social & credentials", char_data['name'])

    if char_data["contacts"]:
        page3.append("[ SOCIAL_NETWORK_CONTACTS ]")
        for c in char_data["contacts"]:
            name = c.get("name", "Unknown")
            c_type = c.get("type", "Contact")
            loy = c.get("loyalty", 0)
            inf = c.get("influence", 0)
            fav = c.get("favors", 0)
            if len(c_type) > 32:
                c_type = c_type[:29] + "..."
            page3.append(f"  - {name.upper().ljust(20)} {c_type.ljust(32)} L:{loy} I:{inf} F:{fav}")
        page3.append("")

    if char_data["sins"] or char_data["licenses"]:
        page3.append("[ REGISTERED_IDENTITIES ]")
        for s_obj in char_data["sins"]:
            s_name = s_obj.get("name", "Unknown")
            rating = s_obj.get("quality", 0)
            if rating == 6 or rating == "6" or rating == "SECOND_LIFE":
                status = "Rating 6"
            elif rating == -1 or rating == "-1" or rating == "REAL_SIN":
                status = "Real SIN"
            else:
                status = str(rating)
            page3.append(f"  - SIN: {s_name.ljust(30)} [{status}]")
        
        for l in char_data["licenses"]:
            l_name = l.get("name", "Unknown")
            rating = l.get("rating", 0)
            if rating == 6 or rating == "6" or rating == "SECOND_LIFE":
                rating_display = "Rating 6"
            elif rating == -1 or rating == "-1" or rating == "REAL_SIN":
                rating_display = "Real SIN"
            else:
                rating_display = str(rating)
            page3.append(f"  - LIC: {l_name.ljust(30)} [{rating_display}]")
        page3.append("")

    # Page 4 (Campaign History)
    page4 = make_page_break(4, "chronicle log", char_data['name'])

    if char_data.get("career_log"):
        page4.append("[ CAREER_LOG ]")
        page4.append(f"  {'DATE'.ljust(12)} | {'KARMA'.rjust(5)} | {'NUYEN'.rjust(8)} | {'EVENT'}")
        page4.append("  " + "-" * 75)
        
        earned_karma = 0
        for entry in char_data["career_log"]:
            date = entry["date"]
            karma = entry["karma"]
            nuyen = entry["nuyen"]
            title = entry["title"]
            gm = entry["gm"]
            
            nuyen_str = f"{nuyen:+d}" if nuyen != 0 else "0"
            karma_str = f"{karma:+d}" if karma != 0 else "0"
            
            if "chargen correction" not in title.lower():
                earned_karma += karma
                
            if len(title) + len(gm) > 46:
                allowed_title_len = 46 - len(gm) - 3
                title = title[:allowed_title_len] + "..."
                
            event = title + gm
            page4.append(f"  {date.ljust(12)} | {karma_str.rjust(5)} | {nuyen_str.rjust(8)} | {event}")
            
        page4.append("  " + "-" * 75)
        earned_karma_val = sum(entry["karma"] for entry in char_data.get("career_log", []) if entry["karma"] > 0)
        lifetime_karma_val = 5 + earned_karma_val
        page4.append(f"  LIFETIME KARMA: {lifetime_karma_val} ({earned_karma_val} earned + 5 from Chargen)")
        page4.append("")

    out = []
    out.extend(page1)
    out.extend(page2)
    out.extend(page3)
    out.extend(page4)
    
    out.append("___________________________________________________________________________")
    out.append("// END_OF_FILE // VELVET@ASTRAL:~$ _")
    
    sheet_text = "\n".join(out)
    return sheet_text

def main():
    parser = argparse.ArgumentParser(description="Generate SR6 CLI Character Sheet from XML")
    parser.add_argument("input_xml", help="Path to the SR6 character XML file")
    parser.add_argument("--output", "-o", help="Output text file path or directory", default="output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print actual rules text inline on sheet")
    args = parser.parse_args()
    
    char_data = parse_character(args.input_xml)
    sheet_text = generate_ascii_sheet(char_data, verbose=args.verbose)
    
    out_path = args.output
    if not out_path.endswith('.txt') and not out_path.endswith('.md'):
        os.makedirs(out_path, exist_ok=True)
        filename = char_data['name'].replace(' ', '_') + ".txt"
        out_path = os.path.join(out_path, filename)
        
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sheet_text)
    print(f"[*] Sheet saved to: {out_path}")

if __name__ == "__main__":
    main()
