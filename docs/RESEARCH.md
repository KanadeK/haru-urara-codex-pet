# Character and project research

Research snapshot: **2026-07-30**.

## Decision

The selected character is **Haru Urara from *Umamusume: Pretty Derby***.

This decision required all three of the following:

1. an existing, officially documented anime/game character rather than an
   invented mascot;
2. clear current popularity and an audience outside a narrow machine or
   developer niche;
3. no Haru Urara Codex pet found in the dated repository, code, gallery, and
   local-project checks below.

The result is carefully worded as **“no matching Codex pet was found in this
search”**. GitHub search cannot prove that no private, deleted, unindexed, or
differently named implementation exists.

## Existence and popularity evidence

- The [official Haru Urara character page](https://umamusume.jp/character/haruurara/)
  documents the character and her defining cheerful personality.
- The [official first-season anime archive](https://anime-umamusume.jp/archive/1st/character/20.html)
  establishes that she is an existing anime character, not a project-created
  approximation.
- [GameSpot reported the global PC launch's strong Steam performance](https://www.gamespot.com/articles/umamusume-pretty-derby-is-galloping-up-the-charts-on-steam/1100-6533094/)
  in July 2025 and specifically discussed the attention around Haru Urara.
- [PC Gamer included the game in its 2026 anime-game recommendations](https://www.pcgamer.com/the-best-anime-games-on-pc/),
  supporting continued international visibility rather than a one-day spike.

These sources support the popularity judgment. They do not guarantee GitHub
stars; repository traction still depends on product quality, discoverability,
maintenance, and community fit.

## Duplicate search

The following read-only searches were run on 2026-07-30.

### GitHub repositories

```text
gh search repos "haru urara codex pet" --limit 100 --json nameWithOwner,url
gh search repos "haruurara codex pet" --limit 100 --json nameWithOwner,url
gh search repos "haru urara desktop pet" --limit 100 --json nameWithOwner,url
```

Result relevant to a Haru Urara Codex pet: **none found**.

### GitHub code

```text
gh search code "Haru Urara spriteVersionNumber" --limit 100
gh search code "Haruurara spritesheetPath" --limit 100
gh search code "Haru Urara CodexPet" --limit 100
gh search code "Haru Urara" --repo crafter-station/petdex --limit 100
```

Result relevant to a Haru Urara Codex pet: **none found**.

The public
[awesome-codex-pet gallery](https://github.com/legeling/awesome-codex-pet)
and [Petdex](https://github.com/crafter-station/petdex) were also inspected.
Characters already represented there or in standalone repositories were
rejected, including options such as Frieren, Bocchi, Anya, Hatsune Miku, and
Reimu.

### Current workspace and prior project concepts

The existing project directory inventory and previous project registry were
checked before initialization. During research, another local task created a
Gold Ship pet, so that candidate was discarded rather than racing or modifying
the parallel work. The new repository was created only after Haru Urara passed
both the local and remote checks.

## Why this is not a duplicate in product scope

A character choice alone is not a product. The repository's durable technical
differentiator is **PetSight**:

- audits all 74 populated v2 cells (including the dedicated neutral look frame)
  across four color-vision modes and two backgrounds;
- detects edge-contrast failures, inert and duplicate frames, scale pops,
  baseline jumps, coverage errors, hidden RGB, and chroma residue;
- emits JSON, PNG, and HTML evidence;
- is coupled to a safe deterministic packager and a recoverable installer.

The pet demonstrates the tooling, while the tooling provides reusable value to
other pet authors. That avoids a repository whose only function is displaying
a character image.

## Rights boundary

The project uses original unofficial fan-made sprites and does not include
official artwork, ripped game assets, logos, or race numbers. The
[official derivative-work guidelines](https://umamusume.jp/derivativework_guidelines/)
remain authoritative and may change. See [`../ASSET_TERMS.md`](../ASSET_TERMS.md).
