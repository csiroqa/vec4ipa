# engine-ffi Specification

## Purpose

Defines the contract between the desktop front-end and the C engine so that
vectors, reverse fits, inventory data, and scheme metadata stay identical to
the CLI.

## Requirements

### Requirement: Runtime scheme width

The front-end SHALL take the vector width from the loaded scheme at runtime and
SHALL allocate every vector, row, and buffer from that width. It MUST NOT
assume 16 dimensions.

#### Scenario: Load an 18-D scheme

- **WHEN** the front-end loads `tongue.scheme`
- **THEN** it reports 18 dimensions, every row has 18 coordinates, and the two
  derived axes are present.

#### Scenario: Load the default scheme

- **WHEN** the front-end starts without a scheme argument
- **THEN** it reports the compiled default width and consistent row lengths.

### Requirement: Value parity

The front-end SHALL return the same segment count, airstream values, notes,
and vector coordinates as `vec4ipa` for the same input and scheme. Coordinates
MUST agree within 5e-4.

#### Scenario: Forward parity

- **WHEN** the front-end and `vec4ipa` convert `sa` with the same scheme
- **THEN** both return the same number of segments and matching coordinates.

#### Scenario: Reverse parity

- **WHEN** the front-end and `vec2ipa` reverse the same vector
- **THEN** both return the same IPA fit and distance.

### Requirement: Engine argument handling

The front-end SHALL pass UTF-8 scheme and metric paths, school modules,
narrowness, and metric settings to the engine, and SHALL surface engine errors
as user-visible messages.

#### Scenario: Non-ASCII path

- **WHEN** the user loads a scheme or metric file whose path contains Chinese
  characters
- **THEN** the engine opens the file and the front-end reports success.

#### Scenario: Invalid metric

- **WHEN** the user loads a metric file with the wrong number of weights
- **THEN** the front-end reports the engine error and keeps the previous metric
  active.

### Requirement: Safe buffer contract

The front-end SHALL validate finite vector input and SHALL size buffers from
the runtime width and declared segment limit. It MUST NOT read or write outside
those buffers.

#### Scenario: Too many segments

- **WHEN** the input exceeds the engine's segment limit
- **THEN** the front-end reports a limit error instead of truncating silently.

#### Scenario: Non-finite vector

- **WHEN** a reverse input contains `NaN` or infinity
- **THEN** the front-end rejects it before calling the reverse fit.

### Requirement: Serialized engine access

The front-end SHALL serialize calls that read or mutate engine global state, or
SHALL make those calls on the UI thread, so concurrent conversions cannot
corrupt scheme, metric, or module state.

#### Scenario: Concurrent conversions

- **WHEN** two conversions are requested at the same time
- **THEN** they run one after the other and both return results for the same
  loaded scheme.
