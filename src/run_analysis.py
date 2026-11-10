"""Run provenance-separated Pandas / SQLite / Matplotlib exploratory analysis."""
import argparse
import hashlib
import json
import os
import platform
import sqlite3
import tempfile
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'teamfight-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from data_pipeline import load_real, simulate
from validate_data import ROOT, validate_analysis


def markdown_table(frame):
    def cell(value):
        if pd.isna(value):
            return '—'
        if isinstance(value, float):
            return f'{value:.3f}'
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(frame.columns) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |'] +
                     ['| ' + ' | '.join(cell(x) for x in row) + ' |'
                      for row in frame.itertuples(index=False, name=None)])


def summarize(frame, directory, synthetic=False):
    """A database never mixes synthetic and real rows; queries retain provenance."""
    sources = {'synthetic'} if synthetic else {'replay', 'memory'}
    frame = validate_analysis(frame, sources)
    directory.mkdir(parents=True, exist_ok=True)
    frame.to_csv(directory / 'analysis.csv', index=False, lineterminator='\n')
    database = directory / 'teamfights.sqlite'
    if database.exists():
        database.unlink()
    tables = {}
    with sqlite3.connect(database) as connection:
        frame.to_sql('fights', connection, index=False, if_exists='fail', dtype={
            'ult_diff': 'INTEGER', 'fight_won': 'INTEGER', 'fight_duration': 'REAL'})
        connection.execute('CREATE UNIQUE INDEX fight_identity ON fights(match_id, fight_id)')
        for path in sorted((ROOT / 'sql').glob('*.sql')):
            table = pd.read_sql_query(path.read_text(encoding='utf-8'), connection)
            tables[path.stem] = table
            table.to_csv(directory / f'{path.stem}.csv', index=False, lineterminator='\n')
    title = 'SYNTHETIC DEMONSTRATION — assumed relationship' if synthetic else 'Real observations — descriptive only'
    lines = [f'# {title}', '', f'Records: **{len(frame)}**. '
             f'Matches: **{frame.match_id.nunique()}**.', '']
    if synthetic:
        lines += ['These are simulated outcomes, not empirical Overwatch win rates. '
                  'The generator imposes an association; these results cannot validate H1.', '']
    else:
        lines += ['Replay and memory observations remain separate below. Replay is the '
                  'existing annotation label; this pipeline did not independently watch replays. '
                  'The current real sample is insufficient for significance, causal, '
                  'population win-rate, or reliable predictive claims.', '']
        for source in ['replay', 'memory']:
            observed = frame[frame.data_source.eq(source)]
            n_known = observed.ult_diff.notna().sum()
            n_levels = observed.ult_diff.nunique()
            lines += [f'{source}: N={len(observed)} fights; ultimate difference recorded '
                      f'for N={n_known}, with {n_levels} distinct recorded values.']
            if n_levels < 2:
                lines += ['H1 cannot be evaluated in this source: no variation in recorded ultimate difference.']
            lines += ['']
    for name, table in tables.items():
        lines += [f'## {name.replace("_", " ")}', '', markdown_table(table), '']
        if table.empty:
            lines += ['No eligible observations.', '']
    counts = frame.data_source.value_counts()
    lines += ['## Coverage and interpretation', '']
    for source in sorted(sources):
        lines += [f'- {source}: N={counts.get(source, 0)} annotated fights.']
    lines += ['', '- Rates use only known outcomes; n_outcomes is their denominator. '
              'Missing outcomes never become losses.',
              '- Ultimate differences require both recorded readiness counts. '
              'Unknown advantages are excluded only from the ultimate grouping.',
              '- H1 concerns readiness immediately before engagement. Existing timestamps '
              'need replay audit to establish that timing consistently.',
              '- First pick occurs during combat. Duration and outcome are measured '
              'after the fight. These are descriptive variables, not pre-fight predictors.',
              '- H2 (positioning) and H3 (coordination) remain qualitative: notes are '
              'retained, with no invented quantitative scores.',
              '- Fights within matches are correlated; maps, compositions, rank, patch, '
              'and selection may confound any observed association.',
              '- No imputation, significance test, causal estimate, or predictive model is used.', '',
              '![Ultimate economy and outcome](ult_outcomes.png)', '',
              '![Observation completeness](completeness.png)', '']
    (directory / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    plot_ult(tables['by_ult_diff'], directory, title)
    plot_completeness(tables['missingness'], directory, title)


def plot_ult(table, directory, title):
    fig, axis = plt.subplots(figsize=(9, 5), layout='constrained')
    for (source, confidence), group in table.groupby(['data_source', 'confidence'], sort=True):
        axis.plot(group.ult_diff, group.win_rate, marker='o', label=f'{source}, {confidence}')
        for row in group.itertuples(index=False):
            if pd.notna(row.win_rate):
                axis.annotate(f'n={row.n_outcomes}/{row.n_fights}',
                              (row.ult_diff, row.win_rate), xytext=(0, 9),
                              textcoords='offset points', ha='center', fontsize=8)
    if table.empty:
        axis.text(.5, .5, 'No known ultimate differences', ha='center', transform=axis.transAxes)
    else:
        axis.legend(loc='lower right')
    axis.set(xlabel='Pre-fight ultimate difference (UT − enemy)', ylabel='Win fraction among known outcomes',
             ylim=(-.08, 1.18), title=title + '\nLabels: known outcomes / fights in each group')
    axis.grid(alpha=.2)
    fig.savefig(directory / 'ult_outcomes.png', dpi=150, metadata={'Software': 'teamfight-analytics'})
    plt.close(fig)


def plot_completeness(table, directory, title):
    fig, axis = plt.subplots(figsize=(10, 5), layout='constrained')
    if table.empty:
        axis.text(.5, .5, 'No observations', ha='center', transform=axis.transAxes)
    else:
        labels = [f'{r.data_source}/{r.confidence}\n{r.variable}' for r in table.itertuples()]
        bars = axis.bar(range(len(table)), table.n_known, color='#287b8e')
        axis.set_xticks(range(len(table)), labels, rotation=45, ha='right', fontsize=8)
        for bar, row in zip(bars, table.itertuples()):
            axis.annotate(f'{row.n_known}/{row.n_fights}',
                          (bar.get_x() + bar.get_width()/2, bar.get_height()),
                          ha='center', va='bottom', fontsize=8)
        axis.set_ylim(0, max(table.n_fights.max() * 1.2, 1))
    axis.set(ylabel='Known observations (labels: known / all)', title=title)
    fig.savefig(directory / 'completeness.png', dpi=150, metadata={'Software': 'teamfight-analytics'})
    plt.close(fig)


def run(raw_path, real_path, memory_path, output, seed=42, n=500, raw_source='replay'):
    output = Path(output)
    real = load_real(raw_path, real_path, memory_path, raw_source)
    synthetic = simulate(n, seed)
    output.mkdir(parents=True, exist_ok=True)
    summarize(real, output / 'real')
    summarize(synthetic, output / 'synthetic', synthetic=True)
    manifest = {
        'seed': seed, 'synthetic_rows': n, 'raw_source': raw_source,
        'inputs_sha256': {label: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                          for label, path in [('raw', raw_path), ('legacy_real', real_path),
                                              ('memory', memory_path)]},
        'versions': {'python': platform.python_version(), 'pandas': pd.__version__,
                     'matplotlib': matplotlib.__version__, 'sqlite': sqlite3.sqlite_version},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (output / 'report.md').write_text(
        '# Overwatch teamfight analytics — Phase 1\n\n'
        f'Real annotations: N={len(real)}; synthetic demonstration: N={len(synthetic)}.\n\n'
        '- [Real observations and limitations](real/report.md)\n'
        '- [Synthetic demonstration (assumed relationship)](synthetic/report.md)\n\n'
        'These populations are never pooled. See manifest.json for seed, input hashes, and runtime versions.\n',
        encoding='utf-8')
    return real, synthetic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, default=ROOT / 'data/raw/teamfights_raw.csv')
    parser.add_argument('--real', type=Path, default=ROOT / 'data/real/teamfights.csv')
    parser.add_argument('--memory', type=Path, default=ROOT / 'data/real/teamfights_memory.csv')
    parser.add_argument('--raw-source', choices=['replay', 'memory'], default='replay')
    parser.add_argument('--output', type=Path, default=ROOT / 'output')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--synthetic-rows', type=int, default=500)
    args = parser.parse_args()
    inputs = [args.raw.resolve(), args.real.resolve(), args.memory.resolve()]
    if any(path.is_relative_to(args.output.resolve()) for path in inputs):
        parser.error('--output must not contain source inputs')
    try:
        real, synthetic = run(args.raw, args.real, args.memory, args.output,
                              args.seed, args.synthetic_rows, args.raw_source)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Analysis failed: {error}\n')
    print(f'Real records: {len(real)}; synthetic records: {len(synthetic)}')
    print(f'Report: {args.output / "report.md"}')


if __name__ == '__main__':
    main()
