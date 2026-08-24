# Shadowrun 6e Portfolio — Velvet

This repository contains the interactive character dossier, career ledger, rules cheat sheets, 20 questions questionnaire, and narrative anthology for **Velvet** (Kim Jin-Young), an Elf Shinto/Musok Mystic Adept built for Shadowrun 6th Edition (Sixth World) and active in **Shadowrun Missions** organized play.

The project is compiled into a responsive, high-performance book using **Quarto** and powered by [`sr6-core`](https://github.com/zeshanrajput/sr6-core).

---

## Project Structure

- `velvet_master.yaml`: Authoritative master dossier file containing raw sheet statistics, attributes, qualities, spells, adept powers, and gear.
- `chapters/`: Source chapters for the Quarto story book:
  - `identity_core.md`: Core background history, corporate origin, and character blueprint.
  - `character_build_point_buy.qmd`: Official character creation point buy allocation.
  - `character_sheet.qmd`: Embeds modular plain-text sheets (Base, Combat, Inventory, Powers, Contacts) with PDF card deck and VTT download links.
  - `character_totals.qmd`: Live career totals dashboard tracking Lifetime Karma, Current Karma, Lifetime Nuyen, Available Nuyen, Initiation Grade, Coven Loyalty, Heat, and Contact Registry Sync.
  - `character_log.qmd`: Mission chronicles, GM credits, nuyen rewards, Karma expenditures, and downtime records.
  - `character_purchases.qmd`: Itemized transactions ledger for gear, nanocosmetics, SINs, spells, and lifestyle expenses.
  - `twenty_questions.qmd`: 20 Questions backstory questionnaire detailing trauma, ethics, corporate relations, and identity.
  - `rules_and_downtime.qmd`: Shinto-Musok spellcasting math, drain calculations, and coven downtime protocols.
  - `01_transaction.md` – `09_Tea_in_Tacoma.md`: Narrative background and campaign chapters.
- `output/`: Holds compiled modular text sheets (`output/text/`), Roll20 JSON & XML saves (`output/vtt/`), and PDF card decks (`output/pdf/`).
- `reference/`: Story continuity index (`story_continuity.md`), growth arcs (`story_arc1.md`, `story_arc2.md`), and voice spec (`voice_spec.md`).

---

## Local Development & Ecosystem Sync

`sr6velvet` relies on `sr6-core` for export generation, rules indexing, prose linting, PDF card decks, and CommLink GUI roundtrip synchronization.

1. **Setup Dependencies**:
   ```bash
   uv sync
   ```

2. **Ecosystem & CommLink GUI One-Command Sync**:
   ```bash
   uv run sr6 sync-all
   ```

3. **Export Character Sheets & Printable PDF Card Decks**:
   ```bash
   # Export modular 76-column plain-text sheets
   uv run sr6 export velvet --format=text_modular

   # Export printable PDF Card Deck (4.25" x 5.5" / 4" x 6" Laserjet format)
   uv run sr6 export velvet --format=pdf_deck

   # Export 1-Page Base Sheet PDF
   uv run sr6 export velvet --format=pdf_base
   ```

4. **Character Dossier & Ledger Deep Audit**:
   ```bash
   uv run sr6 characters audit velvet
   ```

5. **Audio Book Narration & Prose Diagnostics**:
   ```bash
   # Generate TTS audio narration for a chapter (Kokoro engine)
   uv run sr6 narrate chapters/01_transaction.md

   # Lint chapter prose for AI buzzwords, em-dash cadence, and tone
   uv run sr6 lint chapters/01_transaction.md

   # Run narrative continuity audit
   uv run sr6 continuity .
   ```

6. **Compile the Quarto Book**:
   ```bash
   uv run quarto render
   ```

