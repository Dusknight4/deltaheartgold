# Delta Heart Gold

Disassembly of Pokémon HeartGold with a unique colour for every individual Pokémon (hue/saturation/value rotated from its personality value, on sprites, battles, the summary screen, the PC box and the overworld follower), ability donors, custom types from IVs, merged FireRed/Crystal data and many fixes!

This is a fork of [pret/pokeheartgold](https://github.com/pret/pokeheartgold). It is published as **two commits on top of upstream**:

1. **Colour mod only** – the personality-based colour rotation in all of its locations. See [docs/COLOR_MOD.md](docs/COLOR_MOD.md) if you only want that feature.
2. **Everything else** – gameplay changes, data merges, crash fixes, removal of the DSProt anti-piracy code, and Windows build support.

**This repository contains no ROMs, saves, compiler or SDK files.** You must supply your own legally obtained Pokémon HeartGold (US) ROM and the proprietary tools exactly as described in [INSTALL.md](INSTALL.md). The ROM this builds is a *modified* game, so it will not match the upstream sha1 below.

---

# Pokémon HeartGold and SoulSilver

This is a WIP disassembly of Pokémon HeartGold and SoulSilver. For instructions on how to set up the repository, please read [INSTALL.md](INSTALL.md).

This repository builds the following ROMs (in their unmodified, upstream form):

* [**pokeheartgold.us.nds**](https://datomatic.no-intro.org/index.php?page=show_record&s=28&n=4787) `sha1: 4fcded0e2713dc03929845de631d0932ea2b5a37`
* [**pokesoulsilver.us.nds**](https://datomatic.no-intro.org/index.php?page=show_record&s=28&n=4788) `sha1: f8dc38ea20c17541a43b58c5e6d18c1732c7e582`

For contacts and other pret projects, see [pret.github.io](https://pret.github.io/).
