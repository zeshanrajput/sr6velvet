---
name: continuity-tracker
description: Audit story continuity, active spirit status, character contacts (Brynne, Vincent, Hana, Ni Ni Xiaolu, Le Tigre), locations, and timeline events across Velvet's narrative anthology.
---

# Story Continuity & Relationship Graph Skill

Use this skill whenever you need to check narrative continuity, audit recurring character contacts (Brynne Taggart, Vincent Grisome, Hana, Ni Ni Xiaolu, Le Tigre, Claudette Laurier), check active spirit/magical bindings, or verify location anchors across story chapters.

## Quick Execution

To generate or inspect the updated continuity index, run:

```powershell
python scripts/continuity_engine.py
```

This updates [reference/story_continuity.md](file:///c:/github/sr6velvet/reference/story_continuity.md) with word counts, entity mention heatmaps, and active entity states.

## Key Tracked Entities & Anchors

1. **Brynne Taggart:** Fixer (Connection 5, Loyalty 1); primary fixer contact managing high-stakes runs and shadow assets.
2. **Vincent Grisome:** Magic Professional (Connection 5, Loyalty 3); academic and talismonger consult on rare magical phenomena.
3. **Hana:** Wuxing Talismonger / Pop Idol (Connection 6, Loyalty 6); close friend, magical supplier, and media icon.
4. **Ni Ni Xiaolu:** Triad Johnson (Connection 3, Loyalty 1); syndicate fixer providing lucrative, dangerous contracts in Seattle/SEA.
5. **Le Tigre:** Epoch Model (Connection 5, Loyalty 1); high-fashion contact in New Orleans and Seattle social spheres.
6. **Claudette Laurier:** Order of the Golden Dawn Librarian (Connection 5, Loyalty 4); keeper of occult texts and esoteric research.
7. **Whiskey:** Street Doc (Connection 2, Loyalty 3); reliable street medicine and cyber/bioware maintenance contact.
8. **Guild of Freelance Assets:** Conclave (Connection 7, Loyalty 8); general shadowrunner network and professional guild.
