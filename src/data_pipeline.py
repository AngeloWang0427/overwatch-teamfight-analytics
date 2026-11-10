"""Input reconciliation and an explicitly assumed simulation."""
import math
import random

import pandas as pd

from validate_data import FIELDS, RAW_FIELDS, read_csv, validate_analysis, validate_raw


def convert_raw(raw, source='replay'):
    if source not in {'replay', 'memory'}:
        raise ValueError('Raw annotations require a real source: replay or memory')
    raw = validate_raw(raw)
    result = pd.DataFrame(index=raw.index, columns=FIELDS, dtype='string')
    for column in ['match_id', 'fight_id', 'map_name', 'fight_won', 'notes']:
        result[column] = raw[column]
    result['ult_diff'] = raw.team_ults_ready - raw.enemy_ults_ready
    result['fight_duration'] = raw.fight_end_sec - raw.fight_start_sec
    result['data_source'] = source
    result['confidence'] = raw.annotation_confidence
    for index in result.index:
        confidence = raw.at[index, 'annotation_confidence']
        provenance = ('Converted from raw annotation; raw confidence='
                      f'{confidence if pd.notna(confidence) else "missing"}; '
                      'first pick not recorded in raw schema.')
        note = result.at[index, 'notes']
        result.at[index, 'notes'] = f'{note} | {provenance}' if pd.notna(note) else provenance
    return validate_analysis(result, {'replay', 'memory'})


def reconcile(raw_analysis, existing):
    """Merge repeated annotations, reject contradictory facts, keep all notes."""
    left = validate_analysis(raw_analysis, {'replay', 'memory'})
    right = validate_analysis(existing, {'replay', 'memory'})
    records = {tuple(row[k] for k in ('match_id', 'fight_id')): row
               for row in left.to_dict('records')}
    rank = {'low': 0, 'medium': 1, 'high': 2}
    for row in right.to_dict('records'):
        key = (row['match_id'], row['fight_id'])
        if key not in records:
            records[key] = row
            continue
        target = records[key]
        for column in FIELDS:
            if column in {'notes', 'confidence', 'match_id', 'fight_id'}:
                continue
            a, b = target[column], row[column]
            if pd.notna(a) and pd.notna(b) and a != b:
                raise ValueError(f'{key}: conflicting {column}: raw={a!r}, existing={b!r}')
            if pd.isna(a):
                target[column] = b
        confidences = [x for x in [target['confidence'], row['confidence']] if pd.notna(x)]
        target['confidence'] = min(confidences, key=rank.get) if confidences else pd.NA
        notes = [str(x) for x in [target['notes'], row['notes']] if pd.notna(x)]
        target['notes'] = ' | Legacy analysis note: '.join(notes) if notes else pd.NA
    return validate_analysis(pd.DataFrame(records.values(), columns=FIELDS), {'replay', 'memory'})


def load_real(raw_path, real_path, memory_path, raw_source='replay'):
    converted = convert_raw(read_csv(raw_path, RAW_FIELDS), raw_source)
    existing = validate_analysis(read_csv(real_path, FIELDS), {'replay', 'memory'})
    combined = reconcile(converted, existing)
    memory = validate_analysis(read_csv(memory_path, FIELDS), {'memory'})
    return validate_analysis(pd.concat([combined, memory], ignore_index=True), {'replay', 'memory'})


def simulate(n=500, seed=42):
    if n < 0:
        raise ValueError('synthetic row count must be nonnegative')
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        diff = rng.randint(-3, 3)
        probability = 1 / (1 + math.exp(-0.35 * diff))
        rows.append(dict(match_id=f'SIM_{i // 10 + 1:03}', fight_id=str(i % 10 + 1),
                         map_name='Simulated', ult_diff=diff, first_pick=pd.NA,
                         fight_won=int(rng.random() < probability), fight_duration=pd.NA,
                         data_source='synthetic', confidence='synthetic',
                         notes='Assumed logistic relationship; not observed match data.'))
    return validate_analysis(pd.DataFrame(rows, columns=FIELDS), {'synthetic'})
