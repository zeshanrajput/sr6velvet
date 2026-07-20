import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import parse_character

def get_character_stats(xml_path="input/Velvet.xml"):
    if not os.path.exists(xml_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        xml_path = os.path.join(base_dir, "input", "Velvet.xml")

    char_data = parse_character(xml_path)
    attrs = char_data["attributes"]
    skills = char_data["skills"]

    sorcery_obj = next((s for s in skills.values() if s.get("id") == "sorcery"), {})
    influence_obj = next((s for s in skills.values() if s.get("id") == "influence"), {})
    conjuring_obj = next((s for s in skills.values() if s.get("id") == "conjuring"), {})

    sorcery_rating = sorcery_obj.get("rating", 6)
    improved_ability_sorcery = sorcery_obj.get("adept_bonus", 3)
    influence_rating = influence_obj.get("rating", 5)
    conjuring_rating = conjuring_obj.get("rating", 5)

    stats = {
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
        "Sorcery": sorcery_rating,
        "Improved_Ability_Sorcery": improved_ability_sorcery,
        "Influence": influence_rating,
        "Conjuring": conjuring_rating,
    }
    return stats

if __name__ == "__main__":
    stats = get_character_stats()
    print("Character Stats:", stats)
