import csv, random, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / 'data/real/teamfights.csv'
SYN = ROOT / 'data/synthetic/teamfights_simulated.csv'
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
FIELDS = ['match_id','fight_id','map_name','ult_diff','first_pick','fight_won','fight_duration','data_source','confidence','notes']

def load_real():
    with REAL.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    problems=[]
    seen=set()
    for i,r in enumerate(rows,2):
        key=(r['match_id'],r['fight_id'])
        if key in seen: problems.append(f'row {i}: duplicate {key}')
        seen.add(key)
        if r['fight_won'] not in ('0','1'): problems.append(f'row {i}: invalid fight_won')
        if r['ult_diff']:
            try:
                if not -5<=int(r['ult_diff'])<=5: problems.append(f'row {i}: ult_diff outside [-5,5]')
            except ValueError: problems.append(f'row {i}: invalid ult_diff')
        if r['first_pick'] not in ('UT','Enemy','Unknown'): problems.append(f'row {i}: invalid first_pick')
        if r['data_source'] not in ('replay','memory'): problems.append(f'row {i}: invalid source')
        if r['confidence'] not in ('high','medium','low'): problems.append(f'row {i}: invalid confidence')
        if r['fight_duration']:
            try:
                if float(r['fight_duration'])<=0: problems.append(f'row {i}: nonpositive duration')
            except ValueError: problems.append(f'row {i}: invalid duration')
    if problems: raise ValueError('\n'.join(problems))
    return rows

def simulate(n=500, seed=42):
    rng=random.Random(seed)
    rows=[]
    for i in range(n):
        diff=rng.randint(-3,3)
        # Assumed probability, NOT estimated from real matches.
        p=1/(1+2.718281828**(-0.35*diff))
        win=int(rng.random()<p)
        rows.append(dict(match_id=f'SIM_{i//10+1:03}',fight_id=str(i%10+1),map_name='Simulated',ult_diff=str(diff),first_pick='Unknown',fight_won=str(win),fight_duration='',data_source='synthetic',confidence='synthetic',notes='Generated under assumed logistic relationship; not observed'))
    with SYN.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    return rows

def summarize(rows, label):
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE fights (ult_diff INTEGER, fight_won INTEGER)')
    db.executemany('INSERT INTO fights VALUES (?,?)',[(int(r['ult_diff']),int(r['fight_won'])) for r in rows if r['ult_diff']!=''])
    groups=db.execute('SELECT ult_diff,COUNT(*),ROUND(AVG(fight_won)*100,1) FROM fights GROUP BY ult_diff ORDER BY ult_diff').fetchall()
    db.close()
    return label,groups

def main():
    real=load_real()
    synthetic=simulate()
    lines=['# Teamfight Analytics — Initial Report','','**Important:** The synthetic results below are a software demonstration, not empirical evidence about Overwatch.','','## Real data','',f'Records: **{len(real)}**.']
    if real:
        lines += [f'Observed wins: **{sum(int(r["fight_won"]) for r in real)}/{len(real)}**.','']
    else: lines += ['No real observations loaded.','']
    for label,rows in [summarize(real,'Real'),summarize(synthetic,'Synthetic')]:
        lines += [f'## {label}: ultimate advantage and outcome','','| Ult difference | N | Win rate (%) |','|---:|---:|---:|']
        if rows:
            lines += [f'| {diff:+d} | {n} | {rate:.1f} |' for diff,n,rate in rows]
        else: lines += ['| No observed ult_diff | — | — |']
        lines.append('')
    lines += ['## Limitations','','- Real sample is currently too small for reliable statistical inference.','- Observations from one team/match are correlated.','- Memory-based estimates should be separated from replay-verified records.','- First pick happens during the fight; it is not a pre-fight predictor.','- The synthetic generator assumes an effect of ult difference by construction; it cannot validate that effect.']
    report=OUT/'report.md';report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Real records: {len(real)}; synthetic records: {len(synthetic)}')
    print(f'Report: {report}')

if __name__=='__main__':main()
