# Donatural (Ao Vivo) — Performer Research

## Recording
- **DB ID:** add71fe0-4bbf-4102-af55-d2e2b3178c38
- **Title:** Minha Saudade (Ao Vivo)
- **Song:** Minha Saudade (composed by João Donato & João Gilberto)
- **MusicBrainz Recording ID:** 9cdbdc17-f55d-4639-8937-2a706e0b22bc
- **MusicBrainz Release ID:** b2217b74-d4c8-4b5c-8319-89ddaeb90527
- **Spotify Track ID:** 0kTcod5WMzDRp0evvE2L57
- **Spotify Album ID:** 69sBJHQWjXQiMj9OiKZxvC
- **Label:** Biscoito Fino
- **Recording Date:** 2024-08-16 (in DB), but actually recorded January 10, 2005
- **Venue:** Espaço Cultural Sérgio Porto, Humaitá, Rio de Janeiro

## Context
The 2024 streaming release "Donatural (Ao Vivo)" on Biscoito Fino is the audio extracted from the 2005 DVD "Donatural — João Donato ao vivo". The concert was filmed and originally released as DVD only. The 2024 release date is the digital distribution date, not the performance date.

Track 12 "Minha Saudade" is a João Donato solo track (no guest artist). MusicBrainz has zero artist relationships on this recording — only the artist credit (João Donato as leader).

## Identified Personnel (from DVD liner notes)

| Performer | Instrument | MusicBrainz Artist ID | Notes |
|-----------|-----------|----------------------|-------|
| João Donato | piano/keyboards | 9006dc24-d048-496b-8a82-e52c291db66c | Leader, already in DB |
| Donatinho | keyboards | — | João Donato's son |
| Luiz Alves | acoustic & electric bass | — | |
| Robertinho Silva | drums | — | |
| Cidinho | percussion | — | May be listed as "Sidinho Moreira" on Amazon |
| Jessé Sadoc | trumpet & flugelhorn | — | Amazon lists as "Jess Sadoc" |
| Ricardo Pontes | saxophone & flute | — | |

## Guest Artists on Other Tracks (not on track 12)
- Joyce Moreno — tracks 2-3
- Leila Pinheiro — tracks 5-6
- Emílio Santiago — track 7
- Angela Ro Ro — track 8
- Gilberto Gil — tracks 10-11
- Marcelinho da Lua — track 13
- Marcelo D2 — track 15

## Sources
- DVD credits via Brazilian music blog: https://musicaelvaaalma.blogspot.com/2014/08/joao-donato-17-discos.html
- Amazon DVD listing (names Sidinho Moreira, Jess Sadoc, Ricardo Pontes): https://www.amazon.com/Joao-Donato-Donatural-Jo%C3%A3o/dp/B000BP2Y94
- MusicBrainz release: https://musicbrainz.org/release/b2217b74-d4c8-4b5c-8319-89ddaeb90527
- MusicBrainz recording: https://musicbrainz.org/recording/9cdbdc17-f55d-4639-8937-2a706e0b22bc

## TODO
- Add a `source` column to `recording_performers` table to distinguish MusicBrainz-imported vs manually-added performers (mirrors the `recording_date_source` pattern on `recordings`)
- Look up MusicBrainz artist IDs for the sidemen before inserting
- Consider fixing the recording date to 2005-01-10 (actual performance) vs 2024-08-16 (digital release)
