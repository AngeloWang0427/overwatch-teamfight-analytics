"""CSV contracts shared by conversion, simulation, and the CLI validator."""
import argparse
import csv
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['match_id', 'fight_id', 'map_name', 'ult_diff', 'first_pick',
          'fight_won', 'fight_duration', 'data_source', 'confidence', 'notes']
RAW_FIELDS = ['match_id', 'fight_id', 'map_name', 'map_mode', 'side',
              'fight_start_sec', 'fight_end_sec', 'team_comp', 'enemy_comp',
              'team_ults_ready', 'enemy_ults_ready', 'team_alive', 'enemy_alive',
              'fight_won', 'annotation_confidence', 'notes']


def read_csv(path, fields):
    """Only empty cells mean missing; literal text such as NA stays intact."""
    path = Path(path)
    with path.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.reader(stream))
    if not rows or rows[0] != fields:
        raise ValueError(f'{path}: expected columns in order: {", ".join(fields)}')
    for number, row in enumerate(rows[1:], 2):
        if len(row) != len(fields):
            raise ValueError(f'{path}: row {number}: expected {len(fields)} cells, got {len(row)}')
    return pd.DataFrame(rows[1:], columns=fields, dtype='string').replace('', pd.NA)


def _validate(frame, fields, numerical, required, choices):
    if list(frame.columns) != fields:
        raise ValueError(f'Expected columns in order: {", ".join(fields)}')
    result = frame.copy().astype('string').replace('', pd.NA)
    problems = []

    def fail(mask, column, reason):
        for index in np.flatnonzero(mask.fillna(False).to_numpy(dtype=bool)):
            problems.append(f'row {index + 2}: {column}: {reason}')

    for column in required:
        fail(result[column].isna() | result[column].str.strip().eq(''), column, 'required')
    fail(result.duplicated(['match_id', 'fight_id'], keep=False),
         'match_id/fight_id', 'duplicate fight identifier')
    for column, allowed in choices.items():
        fail(result[column].notna() & ~result[column].isin(allowed), column,
             f'expected one of {sorted(allowed)} or an empty cell when optional')
    for column, (low, high, integer, exclusive_low) in numerical.items():
        original = result[column]
        values = pd.to_numeric(original, errors='coerce').astype('Float64')
        invalid = original.notna() & (values.isna() | ~np.isfinite(values))
        invalid |= values.le(low) if exclusive_low else values.lt(low)
        if high is not None:
            invalid |= values.gt(high)
        if integer:
            invalid |= values.mod(1).ne(0)
        fail(invalid, column, f'expected finite {"integer" if integer else "number"} '
             f'{">" if exclusive_low else ">="} {low}'
             + (f' and <= {high}' if high is not None else ''))
        result[column] = values
    if problems:
        raise ValueError('\n'.join(problems))
    for column, (_, _, integer, _) in numerical.items():
        if integer:
            result[column] = result[column].astype('Int64')
    return result


def validate_analysis(frame, allowed_sources=None):
    result = _validate(
        frame, FIELDS,
        {'ult_diff': (-5, 5, True, False), 'fight_won': (0, 1, True, False),
         'fight_duration': (0, None, False, True)},
        ['match_id', 'fight_id', 'data_source'],
        {'data_source': {'replay', 'memory', 'synthetic'},
         'first_pick': {'UT', 'Enemy', 'Unknown'},
         'confidence': {'high', 'medium', 'low', 'synthetic'}})
    synthetic = result.data_source.eq('synthetic')
    if (synthetic != result.confidence.eq('synthetic').fillna(False)).any():
        raise ValueError('confidence must be synthetic exactly when data_source is synthetic')
    if (result.data_source.eq('memory') &
            (result.notes.isna() | result.notes.str.strip().eq(''))).any():
        raise ValueError('memory observations require notes describing recollection uncertainty')
    if allowed_sources is not None and not result.data_source.isin(allowed_sources).all():
        raise ValueError(f'data_source: this input permits only {sorted(allowed_sources)}')
    result['first_pick'] = result.first_pick.replace('Unknown', pd.NA)
    return result


def validate_raw(frame):
    result = _validate(
        frame, RAW_FIELDS,
        {**{name: (0, None, False, False) for name in ('fight_start_sec', 'fight_end_sec')},
         **{name: (0, 5, True, False) for name in
            ('team_ults_ready', 'enemy_ults_ready', 'team_alive', 'enemy_alive')},
         'fight_won': (0, 1, True, False)},
        ['match_id', 'fight_id'],
        {'annotation_confidence': {'high', 'medium', 'low'}})
    invalid = (result.fight_end_sec <= result.fight_start_sec).fillna(False)
    if invalid.any():
        rows = ', '.join(str(i + 2) for i in np.flatnonzero(invalid.to_numpy(dtype=bool)))
        raise ValueError(f'row(s) {rows}: fight_end_sec must exceed fight_start_sec')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path, default=ROOT / 'data/raw/teamfights_raw.csv')
    parser.add_argument('--schema', choices=['raw', 'analysis'], default='raw')
    args = parser.parse_args()
    try:
        if args.schema == 'raw':
            frame = validate_raw(read_csv(args.path, RAW_FIELDS))
        else:
            frame = validate_analysis(read_csv(args.path, FIELDS))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Validation failed: {error}\n')
    print(f'Valid {args.schema} CSV: {len(frame)} teamfights')


if __name__ == '__main__':
    main()
