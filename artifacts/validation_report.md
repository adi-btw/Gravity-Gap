# Validation report: E2 bounds models (M1-M3)

Generated 2026-11-15T01:16:05+00:00 by `python -m engine.validation` (engine 0.1.0). Model versions: M1 `2a8ccd37105c`, M2 `d3f1ae64f2c0`, M3 `3e3a8c2d84ca`.

All numbers are out-of-fold (5-fold, seed 0) on microgravity PSI data. They measure how well each model interpolates *within* its own investigation; they say nothing about partial gravity, which no PSI test covers (see ADR-0005).

## V2 Cross-validation

Leave-one-investigation-out (plan/03 §5) is not possible: FLEX (droplets, heptane/methanol, outcome extinction/completion) and CFI-G (gas spherical burner, ethane/propane/butane, outcome self-extinguished/flow-terminated) share no outcome definition or fuel. We report within-investigation k-fold instead.

### Classifiers (M1, M3)

| Metric | Data | n | positives | AUC | Brier | Brier (base rate) |
|---|---|---|---|---|---|---|
| M1 | FLEX (PSI-69) droplet tests: extinction vs completion (disruption excluded) | 206 | 179 | 0.824 | 0.081 | 0.114 |
| M3 | ACME CFI-G (PSI-159) normal spherical-burner flames (ambient O2) | 133 | 102 | 0.622 | 0.177 | 0.179 |

Calibration (out-of-fold predictions split into terciles):

| Metric | Bin | n | mean predicted | observed rate |
|---|---|---|---|---|
| M1 | 1 | 69 | 0.674 | 0.681 |
| M1 | 2 | 68 | 0.933 | 0.985 |
| M1 | 3 | 69 | 0.988 | 0.942 |
| M3 | 1 | 44 | 0.594 | 0.773 |
| M3 | 2 | 44 | 0.741 | 0.591 |
| M3 | 3 | 45 | 0.947 | 0.933 |

### Quantile model (M2, extinction diameter in mm)

n = 158. Linear quantile regression at q = 0.05 / 0.5 / 0.95 on standardized features.

| Quantity | Model | Constant-quantile baseline |
|---|---|---|
| Pinball loss q=0.05 | 0.0500 | 0.0697 |
| Pinball loss q=0.5 | 0.1627 | 0.4014 |
| Pinball loss q=0.95 | 0.0377 | 0.1042 |
| 5-95% interval coverage (target 0.90) | 0.848 | 0.905 |
| MAE of median (mm) | 0.325 | 0.803 |
| Mean 5-95% width (mm) | 1.286 | |

### Reading these honestly

- M1: AUC 0.824; Brier 0.081 is better than the base-rate baseline 0.114 (margin 0.033).
- M3: AUC 0.622; Brier 0.177 is better than the base-rate baseline 0.179 (margin 0.002; marginal, so treat this model's discrimination as weak).
- M1 is imbalanced (179 extinctions of 206); 61 disruption tests are excluded (ADR-0004), so M1 answers "extinction vs burning to completion" only.
- M3 has a near-separation: every normal flame below ~0.33 O2 self-extinguished, so its low-O2 predictions are close to 1 and the bootstrap band there is narrow; that is the data, not certainty about cabin fires.
- M2 interval coverage 0.848 vs nominal 0.90 (under-covers: treat the band as optimistic).
- Habitat queries with L_mm = 10 use the largest tested droplet (4.67 mm for M1, M2 clip), an edge of the training range.

## Diluted subset (R2 suppression calculator)

The suppression calculator (`engine.suppression`) reads M1 and M2 at CO2 or helium fractions > 0. These are the same out-of-fold predictions as above (same 5 folds), scored only on FLEX rows that used a diluent. Every diluted training row is at 13-24% O2, so nothing here says anything about dilution at 30-34% O2; the ADR-0006 gate withholds numbers there.

| M1 subset | n | extinctions | O2 range | AUC | Brier | Brier (base rate) | mean predicted | observed |
|---|---|---|---|---|---|---|---|---|
| CO2 > 0 | 95 | 87 | 0.14-0.24 | 0.552 | 0.077 | 0.079 | 0.903 | 0.916 |
| He > 0 | 44 | 38 | 0.13-0.24 | 0.921 | 0.085 | 0.118 | 0.874 | 0.864 |
| any diluent | 139 | 125 | 0.13-0.24 | 0.705 | 0.080 | 0.092 | 0.894 | 0.899 |

| M2 subset | n | MAE of median (mm) | MAE baseline (mm) | median bias (mm) | 5-95% coverage |
|---|---|---|---|---|---|
| CO2 > 0 | 77 | 0.314 | 0.850 | 0.140 | 0.844 |
| He > 0 | 35 | 0.382 | 0.693 | 0.134 | 0.886 |
| any diluent | 112 | 0.335 | 0.801 | 0.139 | 0.857 |

- M1 on diluted rows: AUC 0.705, Brier 0.080 vs base rate 0.092. 125 of 139 diluted tests ended in extinction, so the subset is dominated by extinctions and discrimination rests on few completions.
- CO2 > 0: AUC 0.552 is close to chance; the model barely ranks which of these tests went out, so read the curve as the overall trend only (Brier 0.077 vs base rate 0.079).
- The suppression curve shape comes from one linear CO2 (or He) coefficient in a logistic model; it cannot bend. Compare it with the empirical bins in `artifacts/suppression_reference.json`.

## V3 SAFFIRE-II hindcast

`engine.rules` is available (functions: predict_m4, predict_m5). The SAFFIRE-II hindcast (predict 1 g burn extent from microgravity data plus the bridge at g = 9.81, compare with the 1 g columns of `data/clean/psi_saffire_ug_vs_1g.csv`) is owned by DE's M4 rule table; see `artifacts/rules.json` and `tests/test_rules.py`.

## V5 Sensitivity (tornado) summary

For each preset: the atmosphere input that moves the estimate most (O2 +/-0.03, pressure +/-20%), and the physics coefficient that moves the 90% band width most (C_b, k, dT/T, L). k enters only u_eff, not Ri, so it never changes M1-M3 bands.

| Preset | Metric | Estimate | 90% band | Transfer | Top estimate driver (swing) | Top band driver (swing) |
|---|---|---|---|---|---|---|
| iss | M1 | 0.939 | [0.825, 0.982] | high | o2 (0.095) | C_b (0.000) |
| iss | M2 | 4.004 | [2.554, 4.338] | high | o2 (0.651) | C_b (0.000) |
| iss | M3 | 0.972 | [0.945, 0.991] | high | o2 (0.022) | C_b (0.000) |
| exploration | M1 | 0.698 | [0.387, 0.879] | high | o2 (0.318) | C_b (0.000) |
| exploration | M2 | 3.379 | [2.009, 4.119] | high | o2 (0.651) | C_b (0.000) |
| exploration | M3 | 0.947 | [0.884, 0.985] | high | o2 (0.041) | C_b (0.000) |
| lunar_base | M1 | 0.201 | [0.012, 0.684] | low | o2 (0.249) | C_b (0.125) |
| lunar_base | M2 | gated | - | - | Extrapolation: no evidence. The query (O2 0.340, 0.56 atm, CO2 0.00, He 0.00) is more than 2 atmosphere-and-diluent-distance units from every M2 training test; the nearest tested condition is PSI-69 PSI-69:FLEX:45 at O2 0.300, 1.01 atm, CO2 0.00, He 0.00 (atmosphere and diluent distance 2.14). | - |
| lunar_base | M3 | 0.872 | [0.560, 0.985] | low | o2 (0.090) | C_b (0.116) |
| lunar_rover | M1 | 0.201 | [0.007, 0.762] | low | o2 (0.249) | C_b (0.114) |
| lunar_rover | M2 | gated | - | - | Extrapolation: no evidence. The query (O2 0.340, 0.56 atm, CO2 0.00, He 0.00) is more than 2 atmosphere-and-diluent-distance units from every M2 training test; the nearest tested condition is PSI-69 PSI-69:FLEX:45 at O2 0.300, 1.01 atm, CO2 0.00, He 0.00 (atmosphere and diluent distance 2.14). | - |
| lunar_rover | M3 | 0.872 | [0.484, 0.990] | low | o2 (0.090) | C_b (0.111) |
| mars_base | M1 | 0.201 | [0.009, 0.737] | low | o2 (0.249) | C_b (0.143) |
| mars_base | M2 | gated | - | - | Extrapolation: no evidence. The query (O2 0.340, 0.56 atm, CO2 0.00, He 0.00) is more than 2 atmosphere-and-diluent-distance units from every M2 training test; the nearest tested condition is PSI-69 PSI-69:FLEX:45 at O2 0.300, 1.01 atm, CO2 0.00, He 0.00 (atmosphere and diluent distance 2.14). | - |
| mars_base | M3 | 0.872 | [0.510, 0.988] | low | o2 (0.090) | C_b (0.136) |
| earth | M1 | 0.939 | [0.591, 0.995] | low | o2 (0.095) | C_b (0.000) |
| earth | M2 | 4.004 | [1.103, 4.673] | low | o2 (0.651) | C_b (0.000) |
| earth | M3 | 0.972 | [0.895, 0.997] | low | o2 (0.022) | C_b (0.000) |

## S2 Honesty test: held-out tested atmospheres (ADR-0009)

From `artifacts/holdout.json` (generated 2026-11-15T01:15:58+00:00, 200 bootstrap refits per hold-out). Each tested atmosphere is hidden in turn, the model is refitted without it, and the app is asked about that atmosphere with the refitted model (same honesty gate, same band).

Hit rules: M1: Observed share of self-extinctions with a 90% Wilson interval; hit when that interval overlaps the predicted 90% band (lenient for groups of 1-3 tests). strict_hit: the observed share itself is inside the band. M2: Hit when the median observed extinction diameter is inside the predicted 90% band; the share of single held-out diameters inside their own band is pooled as a calibration check.

### Primary: one tested atmosphere at a time

| Metric | groups (tests) | covered | no evidence | skipped | band coverage (overlap rule) | strict (inside band) | no-evidence calls the ungated band would have missed | pooled |
|---|---|---|---|---|---|---|---|---|
| M1 | 74 (206) | 74 | 0 | 0 | 72/74 = 0.97 (90% interval 0.92-0.99) | 7/74 = 0.09 (90% interval 0.05-0.17) | n/a (0 groups) | Brier 0.083 vs training average 0.115 |
| M2 | 65 (158) | 65 | 0 | 0 | 58/65 = 0.89 (90% interval 0.81-0.94) | 58/65 = 0.89 (90% interval 0.81-0.94) | n/a (0 groups) | single diameters inside their band 134/158 = 0.85 (90% interval 0.80-0.89) |
| M3 | 83 (133) | 83 | 0 | 0 | 78/83 = 0.94 (90% interval 0.88-0.97) | 4/83 = 0.05 (90% interval 0.02-0.10) | n/a (0 groups) | Brier 0.175 vs training average 0.182 |

Overall: 222 covered groups, band coverage 208/222 = 0.94 (90% interval 0.90-0.96) (target 0.90).

Worst misses per metric (covered, band missed; gap in probability for M1/M3, mm for M2):

- M1-o2_0.180-p_1.01-co2_0.000-he_0.150: band [0.688, 0.919], observed 0/2 self-extinguished, gap 0.113.
- M1-o2_0.230-p_0.70-co2_0.200-he_0.000: band [0.904, 0.996], observed 1/2 self-extinguished, gap 0.025.
- M2-o2_0.160-p_1.01-co2_0.250-he_0.000: band [1.775, 2.743], observed median 1.52 mm of 3 test(s), gap 0.255.
- M2-o2_0.150-p_1.00-co2_0.000-he_0.000: band [3.193, 4.348], observed median 4.59 mm of 2 test(s), gap 0.242.
- M2-o2_0.140-p_1.00-co2_0.000-he_0.350: band [0.732, 1.874], observed median 1.99 mm of 2 test(s), gap 0.121.
- M3-o2_0.354-p_0.50: band [0.699, 0.916], observed 0/2 self-extinguished, gap 0.124.
- M3-o2_0.371-p_1.00: band [0.753, 0.969], observed 0/1 self-extinguished, gap 0.022.
- M3-o2_0.332-p_0.50: band [0.747, 0.960], observed 0/1 self-extinguished, gap 0.017.

### Wide check: one 0.10-wide O2 band at a time

| Metric | groups (tests) | covered | no evidence | skipped | band coverage (overlap rule) | strict (inside band) | no-evidence calls the ungated band would have missed | pooled |
|---|---|---|---|---|---|---|---|---|
| M1 | 74 (206) | 67 | 7 | 0 | 63/67 = 0.94 (90% interval 0.87-0.97) | 4/67 = 0.06 (90% interval 0.03-0.13) | 0/7 = 0.00 (90% interval 0.00-0.28) | Brier 0.092 vs training average 0.116 |
| M2 | 65 (158) | 63 | 2 | 0 | 49/63 = 0.78 (90% interval 0.68-0.85) | 49/63 = 0.78 (90% interval 0.68-0.85) | 1/2 = 0.50 (90% interval 0.12-0.88) | single diameters inside their band 112/156 = 0.72 (90% interval 0.66-0.77) |
| M3 (weak test) | 83 (133) | 9 | 7 | 67 | 9/9 = 1.00 (90% interval 0.77-1.00) | 0/9 = 0.00 (90% interval 0.00-0.23) | 0/7 = 0.00 (90% interval 0.00-0.28) | Brier 0.176 vs training average 0.100 |

Overall: 139 covered groups, band coverage 121/139 = 0.87 (90% interval 0.82-0.91) (target 0.90).

Worst misses per metric (covered, band missed; gap in probability for M1/M3, mm for M2):

- M1-o2_0.180-p_1.01-co2_0.000-he_0.150: band [0.730, 0.977], observed 0/2 self-extinguished, gap 0.156.
- M1-o2_0.230-p_0.70-co2_0.200-he_0.000: band [0.943, 0.999], observed 1/2 self-extinguished, gap 0.064.
- M1-o2_0.210-p_0.71-co2_0.300-he_0.000: band [0.944, 0.999], observed 2/3 self-extinguished, gap 0.023.
- M2-o2_0.130-p_1.00-co2_0.000-he_0.400: band [0.000, 2.151], observed median 3.54 mm of 1 test(s), gap 1.389.
- M2-o2_0.150-p_0.99-co2_0.000-he_0.300: band [0.241, 2.180], observed median 3.47 mm of 1 test(s), gap 1.290.
- M2-o2_0.160-p_1.00-co2_0.250-he_0.000: band [1.580, 2.801], observed median 3.96 mm of 1 test(s), gap 1.159.

M3: hold-out unit(s) o2_0.30-0.40 not scored: the remaining tests have one outcome only (or fewer than 5 tests), so no model can be refitted.

M3: on these held-out tests the model's Brier score (0.176) is NOT better than predicting the training average (0.100).

### Reading this honestly

- One atmosphere at a time, every held-out group still had a tested neighbour within the gate (the coverage rounding keeps near-duplicate atmospheres such as 1.00 and 1.01 atm apart), so the primary test checks the bands, not the 'no evidence' side of the gate. The wide check is the gate test.
- The overlap rule is lenient for groups of 1-3 tests (a 0/1 or 1/1 group has a wide Wilson interval). The strict rate and the pooled Brier score / single-diameter coverage are the sharper numbers.
- No band or gate was changed because of these results (ADR-0009); any change needs its own ADR.

### Cross-investigation: SAFFIRE-II hindcast (unchanged)

Not discriminative: the bridge scores 7/9, but the constant rule '1 g always burns more' also scores 7/9. It checks the direction of the gravity effect, not whether the bridge can tell samples apart.


## Not done

- V4 literature sanity check (needs E4 papers).
- No partial-gravity ground truth exists; the widened bands (ADR-0005) are a stated assumption, not a validated quantity.
