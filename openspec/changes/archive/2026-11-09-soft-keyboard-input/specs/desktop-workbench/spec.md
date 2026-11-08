# Spec Delta

## ADDED Requirements

### Requirement: Keyboard search

The soft keyboard SHALL filter by symbol text, English feature description, and
Chinese term, and SHALL match Latin text without case sensitivity.

#### Scenario: Match a description

- **WHEN** the user types `plosive`
- **THEN** the visible groups show symbols whose description contains
  `plosive`

#### Scenario: Match a Chinese term

- **WHEN** the UI is Chinese and the user types `擦音`
- **THEN** the visible groups show the fricative symbols

#### Scenario: Match symbol text

- **WHEN** the user types `ʃ`
- **THEN** only symbols containing `ʃ` remain visible

### Requirement: Keyboard group order

The soft keyboard SHALL order consonants by manner then place, non-pulmonic
symbols by airstream, manner, then place, and vowels by tongue position. It
SHALL separate letters from diacritics, order diacritics by tier, include a
dotted-circle key in the diacritics group, and render diacritics larger than
letters.

#### Scenario: Consonant order

- **WHEN** the consonant group is expanded
- **THEN** plosives precede fricatives and places run front to back within one
  manner

#### Scenario: Diacritics group

- **WHEN** the diacritics group is expanded
- **THEN** combining marks are ordered by tier, include the dotted-circle key,
  and use a larger glyph than the letter group

### Requirement: Favorite persistence

The workbench SHALL persist keyboard favorites in
`%APPDATA%\vec4ipa\favorites.txt`, SHALL load them at startup, SHALL save on
every change, SHALL remove duplicates, and SHALL cap the list at 200 entries.

#### Scenario: Survive a restart

- **WHEN** the user favorites `ʃ` and restarts the workbench
- **THEN** `ʃ` is still in the favorites group

#### Scenario: Reject a duplicate

- **WHEN** the same symbol is favorited twice
- **THEN** it appears once in the list and once in the file
