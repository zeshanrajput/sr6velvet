"""
Character Data Engine for Shadowrun 6th Edition (sr6velvet)
Provides clean, dynamic access to Velvet's character attributes, skills, and derived statistics.
"""

import os
import sys
from typing import Dict, Any, Optional
import yaml

_CACHE: Optional[Dict[str, Any]] = None

def get_base_dir() -> str:
    """Returns the absolute path to the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_master_data(yaml_path: str = "velvet_master.yaml", force_reload: bool = False) -> Dict[str, Any]:
    """Loads and caches the master character YAML file."""
    global _CACHE
    if _CACHE is not None and not force_reload:
        return _CACHE

    base_dir = get_base_dir()
    if not os.path.isabs(yaml_path):
        yaml_path = os.path.join(base_dir, yaml_path)

    if os.path.exists(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            _CACHE = yaml.safe_load(f) or {}
    else:
        _CACHE = {}
    return _CACHE

def get_attribute(name: str, default: int = 0) -> int:
    """Retrieves an attribute rating by name (case-insensitive)."""
    data = load_master_data()
    attrs = data.get("attributes", {})
    return attrs.get(name.lower(), default)

def get_skill(name: str) -> Dict[str, Any]:
    """Retrieves a skill definition dictionary by name (case-insensitive)."""
    data = load_master_data()
    skills = data.get("skills", [])
    target = name.lower()
    for s in skills:
        if s.get("name", "").lower() == target or s.get("id", "").lower() == target:
            return s
    return {}

def get_dice_pool(skill_name: str, attribute_name: str) -> int:
    """Calculates base dice pool for a skill + attribute combination."""
    skill_info = get_skill(skill_name)
    skill_rating = skill_info.get("rating", 0)
    attr_rating = get_attribute(attribute_name, 0)
    return skill_rating + attr_rating

def compute_weapon_ar(
    base_ar_str: str,
    is_ranged: bool = True,
    has_smartlink: bool = False,
    is_networked: bool = True,
    has_personalized_grip: bool = False,
    link_fired_count: int = 0,
    is_vehicle_mounted: bool = False
) -> str:
    """
    Dynamically calculates modified Attack Rating (AR) string for any weapon based on:
    - Smartlink (+2 to valid ranges)
    - Networked Smartgun benefit (+1 to valid ranges)
    - Personalized Grip (+1 to Close/Near ranges for ranged; +2 for melee)
    - Link-firing (+1 per secondary weapon)
    - Vehicle/Drone/Cyberarm Weapon Mount (+2 to valid ranges, Double Clutch p. 142)
    """
    parts = base_ar_str.split("/")
    modified = []
    
    base_bonus = 0
    if has_smartlink:
        base_bonus += 2
        if is_networked:
            base_bonus += 1
    if link_fired_count > 0:
        base_bonus += link_fired_count
    if is_vehicle_mounted:
        base_bonus += 2
        
    for idx, p in enumerate(parts):
        p_strip = p.strip()
        if p_strip.isdigit():
            val = int(p_strip) + base_bonus
            if has_personalized_grip:
                if is_ranged and idx in [0, 1]:
                    val += 1
                elif not is_ranged and idx == 0:
                    val += 2
            modified.append(str(val))
        else:
            modified.append(p_strip)
            
    return " / ".join(modified)

def get_processed_weapons() -> Dict[str, Any]:
    """
    Returns processed ranged and close combat weapons with dynamically calculated ARs,
    math breakdowns, burst fire adjustments, and firing mode constraints.
    """
    data = load_master_data()
    weapons_data = data.get("weapons", {})
    
    ranged_processed = []
    for w in weapons_data.get("ranged", []):
        accs = [str(a).lower() for a in w.get("accessories", [])]
        has_smart = w.get("smartlink", False) or any("smartlink" in a for a in accs)
        has_grip = w.get("personalized_grip", False) or any("grip" in a for a in accs)
        link_count = w.get("link_fired_count", 0)
        is_mounted = w.get("is_vehicle_mounted", False) or any("mount" in a for a in accs)
        
        breakdown = [f"Base AR: {w.get('attack_rating', '')}"]
        total_bonus = 0
        if has_smart:
            breakdown.append("Smartlink Base: +2 AR")
            breakdown.append("Networked Smartgun: +1 AR")
            total_bonus += 3
        if has_grip:
            breakdown.append("Personalized Grip: +1 AR (Close & Near ranges only)")
            total_bonus += 1
        if is_mounted:
            breakdown.append("Vehicle/Drone Mount: +2 AR")
            total_bonus += 2

        breakdown.append(f"Total AR Bonus: +{total_bonus} AR")

        mod_ar = compute_weapon_ar(
            w.get("attack_rating", ""),
            is_ranged=True,
            has_smartlink=has_smart,
            is_networked=True,
            has_personalized_grip=has_grip,
            link_fired_count=link_count,
            is_vehicle_mounted=is_mounted
        )
        
        sa_penalty = -1 if is_mounted else -2
        bf_penalty = -2 if is_mounted else -4
        
        def apply_mode_penalty(ar_str: str, pen: int) -> str:
            parts = []
            for p in ar_str.split("/"):
                p_strip = p.strip()
                if p_strip.isdigit():
                    parts.append(str(max(0, int(p_strip) + pen)))
                else:
                    parts.append(p_strip)
            return " / ".join(parts)

        ss_ar_str = mod_ar
        sa_ar_str = apply_mode_penalty(mod_ar, sa_penalty)
        bf_ar_str = apply_mode_penalty(mod_ar, bf_penalty)
        
        base_dv_str = w.get("damage", "3P")
        import re
        m_dv = re.match(r"(\d+)([A-Z]+.*)", base_dv_str)
        if m_dv:
            base_val, suffix = int(m_dv.group(1)), m_dv.group(2)
            sa_dv_str = f"{base_val + 1}{suffix}"
            bf_dv_str = f"{base_val + 2}{suffix}"
        else:
            sa_dv_str = base_dv_str
            bf_dv_str = base_dv_str

        w_copy = dict(w)
        w_copy["modified_attack_rating"] = mod_ar
        w_copy["ss_ar"] = ss_ar_str
        w_copy["sa_ar"] = sa_ar_str
        w_copy["bf_ar"] = bf_ar_str
        w_copy["ss_dv"] = base_dv_str
        w_copy["sa_dv"] = sa_dv_str
        w_copy["bf_dv"] = bf_dv_str
        w_copy["total_ar_bonus"] = total_bonus
        w_copy["math_breakdown"] = breakdown
        w_copy["effective_modes"] = w.get("mode", "SA")
        w_copy["mode_note"] = "Standard sidearm."
        ranged_processed.append(w_copy)

    close_processed = []
    for w in weapons_data.get("close_combat", []):
        accs = [str(a).lower() for a in w.get("accessories", [])]
        has_grip = w.get("personalized_grip", False) or any("grip" in a for a in accs)
        is_mounted = w.get("is_vehicle_mounted", False) or any("mount" in a for a in accs)
        
        breakdown = [f"Base AR: {w.get('attack_rating', '')}"]
        total_bonus = 0
        if has_grip:
            breakdown.append("Personalized Grip (Melee): +2 AR")
            total_bonus += 2
        if is_mounted:
            breakdown.append("Fingertip Cyberarm Mount: +2 AR")
            total_bonus += 2
            
        breakdown.append(f"Total AR Bonus: +{total_bonus} AR")
        
        mod_ar = compute_weapon_ar(
            w.get("attack_rating", ""),
            is_ranged=False,
            has_smartlink=False,
            is_networked=False,
            has_personalized_grip=has_grip,
            is_vehicle_mounted=is_mounted
        )
        w_copy = dict(w)
        w_copy["modified_attack_rating"] = mod_ar
        w_copy["ss_ar"] = mod_ar
        w_copy["sa_ar"] = "N/A"
        w_copy["bf_ar"] = "N/A"
        w_copy["ss_dv"] = w.get("damage", "6P")
        w_copy["sa_dv"] = "N/A"
        w_copy["bf_dv"] = "N/A"
        w_copy["total_ar_bonus"] = total_bonus
        w_copy["math_breakdown"] = breakdown
        w_copy["effective_modes"] = "Melee (Close)"
        w_copy["mode_note"] = "Close Combat Attack."
        close_processed.append(w_copy)

    return {
        "ranged": ranged_processed,
        "close_combat": close_processed
    }

def get_character_stats(yaml_path: str = "velvet_master.yaml") -> Dict[str, Any]:
    """
    Returns Velvet's core attribute and skill ratings as a dictionary.
    Used by identity_core, rules_and_downtime.qmd, etc.
    """
    base_dir = get_base_dir()
    xml_path = os.path.join(base_dir, "input", "Velvet.xml")
    if os.path.exists(xml_path):
        try:
            from main import parse_character
            cd = parse_character(xml_path)
            attrs = cd.get("attributes", {})
            s_map = {sk["id"]: sk for sk in cd.get("skills", {}).values()}
            sorc = s_map.get("sorcery", {})
            inf = s_map.get("influence", {})
            conj = s_map.get("conjuring", {})
            return {
                "Body": attrs.get("BODY", 2),
                "Agility": attrs.get("AGILITY", 3),
                "Reaction": attrs.get("REACTION", 2),
                "Strength": attrs.get("STRENGTH", 2),
                "Willpower": attrs.get("WILLPOWER", 5),
                "Logic": attrs.get("LOGIC", 3),
                "Intuition": attrs.get("INTUITION", 3),
                "Charisma": attrs.get("CHARISMA", 10),
                "Magic": attrs.get("MAGIC", 6),
                "Edge": attrs.get("EDGE", 2),
                "Sorcery": sorc.get("rating", 6),
                "Improved_Ability_Sorcery": sorc.get("adept_bonus", 2),
                "Influence": inf.get("rating", 5),
                "Conjuring": conj.get("rating", 1),
            }
        except Exception as e:
            print(f"[*] Warning reading XML in char_engine: {e}")

    data = load_master_data(yaml_path)
    attrs = data.get("attributes", {})
    
    sorcery_info = get_skill("Sorcery")
    sorcery_rating = sorcery_info.get("rating", 6)
    improved_ability_sorcery = sorcery_info.get("adept_bonus", 2)
    influence_rating = get_skill("Influence").get("rating", 5)
    conjuring_rating = get_skill("Conjuring").get("rating", 1)

    return {
        "Body": attrs.get("body", 2),
        "Agility": attrs.get("agility", 3),
        "Reaction": attrs.get("reaction", 2),
        "Strength": attrs.get("strength", 2),
        "Willpower": attrs.get("willpower", 5),
        "Logic": attrs.get("logic", 3),
        "Intuition": attrs.get("intuition", 3),
        "Charisma": attrs.get("charisma", 10),
        "Magic": attrs.get("magic", 6),
        "Edge": attrs.get("edge", 2),
        "Sorcery": sorcery_rating,
        "Improved_Ability_Sorcery": improved_ability_sorcery,
        "Influence": influence_rating,
        "Conjuring": conjuring_rating,
    }

if __name__ == "__main__":
    stats = get_character_stats()
    print("[*] Velvet Character Stats Loaded:")
    for k, v in stats.items():
        print(f"    - {k}: {v}")
