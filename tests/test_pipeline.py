import hashlib
import sqlite3

import pandas as pd
import pytest

from data_pipeline import convert_raw, load_real, reconcile, simulate
from run_analysis import run, summarize
from validate_data import FIELDS, RAW_FIELDS, ROOT, read_csv, validate_analysis, validate_raw

RAW = ROOT / 'data/raw/teamfights_raw.csv'
REAL = ROOT / 'data/real/teamfights.csv'
MEMORY = ROOT / 'data/real/teamfights_memory.csv'


@pytest.fixture
def observation():
    return pd.DataFrame([dict(match_id='TEST_ONLY', fight_id='1', map_name='Ilios',
                              ult_diff='0', first_pick='', fight_won='1', fight_duration='20',
                              data_source='memory', confidence='low',
                              notes='Test fixture only; uncertain recollection.')], columns=FIELDS)


@pytest.mark.parametrize('column,value', [
    ('ult_diff', '6'), ('ult_diff', '-6'), ('ult_diff', '0.5'), ('ult_diff', 'bad'),
    ('fight_won', '2'), ('fight_won', '-1'), ('fight_won', '0.5'),
    ('fight_duration', '0'), ('fight_duration', '-1'), ('fight_duration', 'inf'),
    ('fight_duration', 'NaN'), ('ult_diff', '-inf'), ('fight_duration', 'abc'),
])
def test_invalid_numbers(observation, column, value):
    observation.loc[0, column] = value
    with pytest.raises(ValueError, match=f'row 2: {column}'):
        validate_analysis(observation)


def test_duplicate_identity_is_match_and_fight(observation):
    with pytest.raises(ValueError, match='duplicate fight identifier'):
        validate_analysis(pd.concat([observation, observation], ignore_index=True))
    other = observation.copy()
    other['match_id'] = 'ANOTHER_TEST'
    assert len(validate_analysis(pd.concat([observation, other]))) == 2


def test_missing_measurements_and_sql_denominators(observation, tmp_path):
    other = observation.copy()
    other['fight_id'] = '2'
    other[['fight_won', 'fight_duration', 'ult_diff', 'first_pick', 'map_name']] = pd.NA
    frame = validate_analysis(pd.concat([observation, other], ignore_index=True))
    assert frame.loc[1, ['fight_won', 'ult_diff', 'fight_duration']].isna().all()
    summarize(frame, tmp_path)
    with sqlite3.connect(tmp_path / 'teamfights.sqlite') as db:
        assert db.execute('SELECT COUNT(*), COUNT(fight_won), AVG(fight_won) FROM fights').fetchone() == (2, 1, 1.0)
        assert db.execute('SELECT fight_won FROM fights WHERE fight_id="2"').fetchone() == (None,)
    summary = pd.read_csv(tmp_path / 'by_source.csv')
    assert summary.loc[0, 'n_fights'] == 2
    assert summary.loc[0, 'n_outcomes'] == 1
    assert summary.loc[0, 'n_durations'] == 1
    assert summary.loc[0, 'win_rate'] == 1
    assert pd.read_csv(tmp_path / 'by_ult_diff.csv').loc[0, 'n_fights'] == 1


def test_all_missing_and_empty_outputs(observation, tmp_path):
    observation[['ult_diff', 'first_pick', 'fight_won', 'fight_duration']] = pd.NA
    summarize(observation, tmp_path / 'missing')
    summary = pd.read_csv(tmp_path / 'missing/by_source.csv')
    assert summary.loc[0, 'n_outcomes'] == 0
    assert pd.isna(summary.loc[0, 'win_rate'])
    summarize(observation.iloc[:0], tmp_path / 'empty')
    summarize(simulate(0), tmp_path / 'empty_synthetic', synthetic=True)
    assert (tmp_path / 'empty/report.md').is_file()


def test_raw_conversion_preserves_missing_and_notes():
    raw = read_csv(RAW, RAW_FIELDS)
    raw.loc[0, ['team_ults_ready', 'fight_end_sec', 'fight_won']] = pd.NA
    converted = convert_raw(raw)
    assert converted.loc[0, ['ult_diff', 'fight_duration', 'fight_won', 'first_pick']].isna().all()
    assert raw.loc[0, 'notes'] in converted.loc[0, 'notes']


@pytest.mark.parametrize('column,value', [('team_ults_ready', '6'), ('enemy_alive', '-1'),
                                         ('team_alive', '2.5'), ('fight_start_sec', 'inf'),
                                         ('fight_end_sec', '10')])
def test_raw_validation(column, value):
    raw = read_csv(RAW, RAW_FIELDS)
    raw.loc[0, column] = value
    with pytest.raises(ValueError, match=column):
        validate_raw(raw)


def test_original_annotations_reconciled_without_modification():
    before = {path: path.read_bytes() for path in [RAW, REAL]}
    frame = load_real(RAW, REAL, MEMORY)
    assert len(frame) == 2
    assert frame.confidence.tolist() == ['medium', 'medium']
    assert frame.first_pick.isna().all()
    assert frame.fight_duration.tolist() == [30, 19]
    for index, raw in read_csv(RAW, RAW_FIELDS).iterrows():
        assert raw.notes in frame.loc[index, 'notes']
        assert read_csv(REAL, FIELDS).loc[index, 'notes'] in frame.loc[index, 'notes']
    assert all(path.read_bytes() == value for path, value in before.items())


def test_conflicting_annotations_rejected():
    converted = convert_raw(read_csv(RAW, RAW_FIELDS))
    legacy = read_csv(REAL, FIELDS)
    legacy.loc[0, 'fight_won'] = '1'
    with pytest.raises(ValueError, match='conflicting fight_won'):
        reconcile(converted, legacy)


def test_synthetic_cannot_enter_real_outputs(tmp_path):
    with pytest.raises(ValueError, match='data_source'):
        summarize(simulate(10), tmp_path / 'real')
    frame = simulate(1)
    frame['confidence'] = 'high'
    with pytest.raises(ValueError, match='confidence'):
        validate_analysis(frame)


def test_synthetic_rejected_at_real_intake(tmp_path):
    path = tmp_path / 'contaminated.csv'
    simulate(2).to_csv(path, index=False)
    with pytest.raises(ValueError, match='data_source'):
        load_real(RAW, path, MEMORY)
    with pytest.raises(ValueError, match='data_source'):
        load_real(RAW, REAL, path)


def test_unrecorded_confidence_and_memory_uncertainty(observation, tmp_path):
    observation['confidence'] = pd.NA
    summarize(observation, tmp_path)
    assert pd.read_csv(tmp_path / 'by_source.csv').loc[0, 'confidence'] == 'unrecorded'
    observation['notes'] = ''
    with pytest.raises(ValueError, match='uncertainty'):
        validate_analysis(observation)


def test_memory_intake_does_not_duplicate_replay(tmp_path):
    memory = read_csv(REAL, FIELDS)
    memory['data_source'] = 'memory'
    memory['notes'] = 'Test fixture; uncertain recollection.'
    path = tmp_path / 'memory.csv'
    memory.to_csv(path, index=False)
    with pytest.raises(ValueError, match='duplicate fight identifier'):
        load_real(RAW, REAL, path)


def test_replay_memory_are_not_pooled(observation, tmp_path):
    replay = observation.copy()
    replay['match_id'] = 'REPLAY_TEST'
    replay['data_source'] = 'replay'
    replay['fight_won'] = '0'
    summarize(pd.concat([observation, replay], ignore_index=True), tmp_path)
    summary = pd.read_csv(tmp_path / 'by_ult_diff.csv').set_index('data_source')
    assert summary.loc['memory', 'win_rate'] == 1
    assert summary.loc['replay', 'win_rate'] == 0
    assert summary.n_fights.tolist() == [1, 1]


def test_csv_contract_and_unknown_marker(tmp_path, observation):
    bad = tmp_path / 'bad.csv'
    bad.write_text(','.join(FIELDS) + '\nwrong,width\n')
    with pytest.raises(ValueError, match='row 2'):
        read_csv(bad, FIELDS)
    bad.write_text('a,b\n')
    with pytest.raises(ValueError, match='expected columns'):
        read_csv(bad, FIELDS)
    observation['first_pick'] = 'Unknown'
    assert validate_analysis(observation).first_pick.isna().all()


def test_pipeline_reproducible_and_separated(tmp_path):
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in [RAW, REAL, MEMORY]}
    for folder in ['one', 'two']:
        run(RAW, REAL, MEMORY, tmp_path / folder, seed=42, n=50)
    first = tmp_path / 'one'
    second = tmp_path / 'two'
    # All artifacts, including database, reports and PNG bytes, are deterministic
    # under the same installed runtime and inputs.
    for path in first.rglob('*'):
        if path.is_file():
            assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()
    for source, expected in [('real', {'replay'}), ('synthetic', {'synthetic'})]:
        with sqlite3.connect(first / source / 'teamfights.sqlite') as db:
            assert {x[0] for x in db.execute('SELECT DISTINCT data_source FROM fights')} == expected
    assert len(pd.read_csv(first / 'real/analysis.csv')) == 2
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    pd.testing.assert_frame_equal(simulate(50, 42), simulate(50, 42))
    assert not simulate(50, 42).equals(simulate(50, 43))
