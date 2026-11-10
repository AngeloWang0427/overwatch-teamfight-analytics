# Synthetic data: demonstration only

The default run generates N=500 rows using Python's local `random.Random(42)`. No real observations are used to estimate generator parameters. Every generated row has `data_source=synthetic`, `confidence=synthetic`, a `SIM_` match identity, and a note stating that it is not observed match data. Real input validators reject synthetic provenance, and real and synthetic SQLite databases are separate.

## Assumptions

1. Ultimate difference is independently sampled with equal probability from the integers -3 through +3. This is an arbitrary demonstration range within the analysis contract's [-5,5], not an empirical distribution.
2. Conditional win probability is assumed to be `p = 1 / (1 + exp(-0.35 * ult_diff))`. The intercept is zero; at equal readiness the assumed probability is 0.5. The coefficient 0.35 is chosen for illustration, not fitted or validated. Readiness quantity ignores ultimate quality and composition.
3. Outcomes are independent Bernoulli draws using that probability. A new uniform draw is used per outcome. The generator draws difference, then outcome, for each row in sequence; this order is part of reproducibility.
4. Every ten rows share an artificial match ID, with fight IDs 1 through 10 (the final match may be partial). This grouping is only an identifier convention; it introduces no match-level dependence or effects.
5. Map is the literal label `Simulated`. First picks and durations are left missing. No temporal, spatial, coordination, patch, composition, skill, or missingness mechanism is simulated.
6. Synthetic confidence is a provenance sentinel, not a claim that simulated observations are high quality real evidence.

## What it demonstrates

The simulation exercises schema validation, grouped SQL counts and conditional win fractions, explicit denominators, missingness summaries, visualizations, separate storage, and Markdown reporting. Repeating a run with the same seed, inputs, dependency versions, and runtime gives identical artifacts in tests. Different operating systems, fonts, or SQLite versions can affect rendered images or database bytes; the manifest records the runtime and input hashes. Dependency versions are pinned.

The plotted relationship follows from the assumed formula. Neither its direction nor its magnitude validates H1, supplies real competitive win rates, or establishes a causal effect. H2 and H3 are not simulated or quantified. There are no significance tests or fitted prediction models. More elaborate simulations would still be methodological demonstrations, requiring empirical validation before competitive claims.
