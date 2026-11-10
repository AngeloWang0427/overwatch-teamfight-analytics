# Annotation protocol and data dictionary

## Unit, identity, and source

One row is one fight from UT's perspective. `(match_id, fight_id)` uniquely identifies a fight; reuse fight numbers across different matches, not within a match. Do not duplicate a replay fight as a memory fight. A reviewed upgrade in provenance should be an explicit annotation revision, not a second observation. Preserve original files and notes.

The original raw CSV and legacy analysis CSV have two overlapping identities. They are intentionally reconciled across files; duplicate keys *within* any input or across the final memory intake fail validation. If known values conflict, the pipeline stops and requires a reviewed correction to an input copy. It never guesses which observation is correct. Raw and legacy notes are both appended into derived notes, including the raw confidence. The lower of two recorded confidences is retained (high > medium > low); missing confidence remains missing unless the other annotation supplies it.

`replay` means an annotation labeled as checked against replay, not automatic verification by this code. `memory` means a real recollection with explicit uncertainty notes, never relabeled as replay based on confidence. `synthetic` is for simulation only. Memory inputs require nonempty notes describing what is uncertain. There are currently no memory observations in the repository.

## Analysis contract (10 columns, exact order)

| Column | Meaning and validation | Timing |
| --- | --- | --- |
| match_id | Required nonblank string; use original match identity | Metadata |
| fight_id | Required nonblank string, unique within match | Metadata |
| map_name | Recorded map; empty when unavailable | Metadata |
| ult_diff | Integer in [-5, 5], UT ready ultimates minus enemy ready ultimates; empty unless both known | Immediately before engagement |
| first_pick | UT or Enemy for the first elimination; empty if unconfirmed; legacy Unknown accepted and normalized to missing | During fight |
| fight_won | UT win=1, loss=0; empty for unknown, ambiguous, or unadjudicated result | After fight |
| fight_duration | Finite positive seconds; empty when either boundary is unavailable | After fight |
| data_source | Required: replay, memory, synthetic | Provenance |
| confidence | Recorded high, medium, low; may be empty if unrecorded; synthetic required for synthetic rows only | Annotation metadata |
| notes | Original narrative and uncertainty; optional except for memory | Qualitative evidence |

Only empty cells are missing in the CSV reader. Literal strings such as NA in map/metadata fields remain text. Nonempty invalid numbers (including NaN and infinity) are errors, not silently coerced into missing. SQLite receives SQL NULL for missing values; Pandas uses nullable dtypes. SQL displays missing confidence as `unrecorded`, without changing the stored analysis value. Neither unknown outcomes nor unknown advantages become zero.

The readiness bound assumes standard five-player teams, with at most five ready ultimates per team; this contract must be reviewed before using other formats. Fractional readiness/alive counts and outcomes are invalid. Positive fractional durations are valid.

## Original raw contract (16 columns, preserved)

`match_id, fight_id, map_name, map_mode, side, fight_start_sec, fight_end_sec, team_comp, enemy_comp, team_ults_ready, enemy_ults_ready, team_alive, enemy_alive, fight_won, annotation_confidence, notes`

Validate IDs, duplicate identities, finite nonnegative timestamps, strictly ordered known boundaries, integer readiness/alive counts in [0,5], outcomes in {0,1}, and optional confidence in {high,medium,low}. All measurements may be empty. The validator does not assert that narrative notes or hero labels are accurate. Extra raw fields stay in the immutable raw file rather than being discarded or invented in the analysis schema.

Conversion computes `ult_diff = team_ults_ready - enemy_ults_ready` and `fight_duration = fight_end_sec - fight_start_sec` only when both operands are recorded. No first-pick column exists in the raw contract, so conversion leaves first pick missing. A compatible existing analysis annotation may supply a genuinely recorded first pick. Notes are never parsed into quantitative positioning, coordination, readiness, or elimination claims.

## Collection guidance

For future replay annotations, record the replay identity, patch/rank where available, map, perspective, fight boundaries, and a readiness snapshot immediately before the engagement. Define a start as the first committed engagement after a reset; define an end as decisive resolution or disengagement. Staggers and overlapping engagements need a written adjudication note. These are prospective guidelines; they do not certify that older annotations followed the same definitions.

Check the first elimination directly in replay; simultaneous or unclear first eliminations stay missing. Adjudicate the teamfight outcome independently of eventual map victory; ambiguous outcomes stay missing. Use high confidence only for clearly checked observations, medium for partially ambiguous annotations, and low for uncertain observations, with specifics in notes. Confidence is a qualitative label, not a numeric probability or analysis weight.

For memory observations, record only remembered facts. Leave unknown readiness, first pick, durations, and outcomes empty. Describe uncertainty explicitly. To add a source that has no observations, supply the required header with no data rows. Test fixtures belong under tests and must never be copied into real inputs.
