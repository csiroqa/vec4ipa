# Spec Delta

## ADDED Requirements

### Requirement: Exact module set

The wrapper SHALL reset the optional module flags, apply an ordered list of
module names in one call, and report the enabled modules. Always-on modules
SHALL stay unaffected, and the CLI enable-only flags SHALL keep their behavior.

#### Scenario: Apply an exact set

- **WHEN** the front-end applies `americanist` and `sinologist` in that order
- **THEN** only those two school modules are enabled and their order is kept

#### Scenario: Report the enabled set

- **WHEN** the front-end asks for the enabled modules
- **THEN** the reply lists the enabled module names in enable order

#### Scenario: CLI behavior unchanged

- **WHEN** a CLI tool starts with `--americanist`
- **THEN** it enables that school exactly as before
