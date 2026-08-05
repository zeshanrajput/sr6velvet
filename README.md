# Shadowrun 6e Portfolio - Velvet

This repository contains the interactive character dossier, downtime tracking system, rules cheatsheets, and narrative log for **Velvet** (Kim Jin-Young), a Dalakitnon Shinto/Musok Mage character built for Shadowrun 6th Edition (Sixth World) and active in **Shadowrun Missions** organized play.

The project is compiled into a polished, responsive book using **Quarto** and powered by [`sr6-core`](https://github.com/zeshanrajput/sr6-core).

---

## Project Structure

- `velvet_master.yaml`: Authoritative master dossier file containing raw sheet statistics, attributes, qualities, spells, and gear.
- `chapters/`: The source files for the Quarto book:
  - `identity_core.md`: Metatype, background history, story context, and identity core.
  - `character_sheet.qmd`: Embeds the generated plain-text character sheet.
  - `rules_and_downtime.qmd`: Spellcasting math, summoning/binding calculations, and quickening metamagic cheat sheets.
  - `character_log.qmd`: Complete run history, karma trackers, nuyen ledgers, and contact lists.
- `input/`: Character source files (XML export from Chummer6/Genesis and Foundry JSON datasets).
- `output/`: Holds compiled text character sheet (`velvet_sheet.txt`), Roll20 JSON (`velvet_sheet.json`), and CommLink XML (`velvet_sheet.xml`).
- `reference/`: Story continuity indices and narrative standards documents.

---

## Local Development & Ecosystem Sync

`sr6velvet` relies on `sr6-core` for export generation, rules indexing, prose linting, and CommLink GUI roundtrip synchronization.

1. **Setup Dependencies**:
   ```bash
   uv sync
   ```

2. **Build Character Exports**:
   ```bash
   uv run sr6 export velvet --format=vtt
   ```

3. **Ecosystem & CommLink GUI Sync**:
   ```bash
   uv run sr6 sync-all
   ```

4. **Compile the Quarto Book**:
   ```bash
   quarto render
   ```
