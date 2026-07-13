# Static inference on IPC Phase 3+ — findings

Dataset: `merged_adm1_wide.parquet` | rows=9869 | features=33 | areas=625 | target mean=21.9%

Models handle missing values natively (no imputation). Validation avoids spatial leakage (test areas unseen). `wfp_obs_count` excluded (data-density proxy).


## Model leaderboard — geographic hold-out (unseen adm1 areas)

```
                         MAE    RMSE     R2
random_forest          7.483  10.795  0.597
xgboost                7.494  10.872  0.592
lightgbm               7.596  11.041  0.579
baseline_country_mean  8.355  11.646  0.531
decision_tree          8.586  12.275  0.479
```


## Model leaderboard — random hold-out (rows shuffled, same 80/20 size)

```
                         MAE    RMSE     R2
xgboost                6.462   8.861  0.726
random_forest          6.582   9.061  0.713
lightgbm               6.710   9.140  0.708
decision_tree          7.625  10.759  0.596
baseline_country_mean  8.233  11.362  0.549
```


R² gap (random − geographic) — how much spatial autocorrelation inflates scores:

```
  random_forest            0.713 − 0.597 = ++0.116
  xgboost                  0.726 − 0.592 = ++0.134
  lightgbm                 0.708 − 0.579 = ++0.129
  baseline_country_mean    0.549 − 0.531 = ++0.018
  decision_tree            0.596 − 0.479 = ++0.116
```


## Model leaderboard — GroupKFold CV (5-fold by area, out-of-fold)

```
                         MAE    RMSE     R2
lightgbm               7.558  10.454  0.621
xgboost                7.596  10.636  0.608
random_forest          7.658  10.723  0.601
baseline_country_mean  8.363  11.362  0.552
decision_tree          8.595  12.090  0.493
```


## Country ablation — GroupKFold CV WITHOUT Country feature

```
                  MAE    RMSE     R2
xgboost         8.459  11.376  0.551
lightgbm        8.530  11.411  0.549
random_forest   8.979  11.965  0.504
decision_tree  10.393  14.033  0.317
```


R² drop when Country is removed:

```
xgboost          0.056
lightgbm         0.072
random_forest    0.098
decision_tree    0.176
```


## Top drivers — mean(|SHAP|), XGBoost (with Country)

```
Country                                    4.834
idp_rate                                   4.078
acled_political_violence_events_per100k    1.823
wfp_price                                  1.212
year                                       0.986
acled_total_events_per100k                 0.906
rain_1m                                    0.850
rain_1m_sum                                0.769
ndvi_vim                                   0.703
gdelt_material_conflict_mentions           0.653
ndvi_viq                                   0.615
rain_3m                                    0.607
gdelt_verbal_coop_tone                     0.581
gdelt_verbal_coop_mentions                 0.545
gdelt_material_conflict_events             0.528
```


Best-ranked GDELT media feature: **gdelt_material_conflict_mentions** at rank 10 of 33. GDELT feature ranks: [10, 13, 14, 15, 18, 21, 22, 25, 26, 27, 29, 32].


Driver group of each top-15 SHAP feature:

```
  Country                                    context
  idp_rate                                   displacement
  acled_political_violence_events_per100k    conflict
  wfp_price                                  prices
  year                                       context
  acled_total_events_per100k                 conflict
  rain_1m                                    climate
  rain_1m_sum                                climate
  ndvi_vim                                   climate
  gdelt_material_conflict_mentions           media(GDELT)
  ndvi_viq                                   climate
  rain_3m                                    climate
  gdelt_verbal_coop_tone                     media(GDELT)
  gdelt_verbal_coop_mentions                 media(GDELT)
  gdelt_material_conflict_events             media(GDELT)
```


## Per-country R2 — geographic hold-out (sorted by XGBoost)

```
model    xgboost  random_forest  lightgbm  baseline_country_mean
Country                                                         
SDN        0.788          0.803     0.753                 -0.084
KEN        0.608          0.593     0.597                 -0.002
NGA        0.394          0.366     0.455                 -0.012
SLV        0.351          0.216     0.276                 -0.037
SOM        0.336          0.355     0.354                 -0.000
YEM        0.264          0.264     0.239                 -0.039
NAM        0.237          0.321     0.261                 -0.007
AFG        0.220          0.284     0.247                 -0.000
HTI        0.194         -0.869     0.123                 -0.012
TCD        0.182          0.202     0.197                 -0.005
HND        0.157          0.376     0.189                 -0.041
BGD        0.138         -0.027    -0.054                 -1.424
GMB        0.123          0.298     0.047                 -0.250
CAF        0.072          0.100     0.167                 -0.317
COD        0.071          0.120     0.097                 -0.033
ZWE        0.068         -0.091    -0.858                 -0.001
GTM        0.046          0.133     0.050                 -0.076
MOZ        0.003          0.041     0.079                 -0.010
TGO       -0.026         -2.101    -0.427                 -0.574
MRT       -0.054         -0.753    -0.262                 -0.018
LBR       -0.066          0.054     0.039                 -0.130
GNB       -0.083         -0.097    -0.060                 -0.005
BEN       -0.191         -1.410    -0.199                 -0.043
GIN       -0.288         -0.369    -0.158                 -0.008
TLS       -0.400         -0.178    -0.562                 -0.022
PAK       -0.446         -0.112    -0.509                 -0.061
SSD       -0.521         -0.463    -0.612                 -0.143
CIV       -0.544         -0.329    -0.652                 -0.305
CPV       -0.731         -0.394    -0.384                 -0.003
ECU       -0.798          0.120    -1.499                 -0.002
TZA       -1.198         -1.810    -2.179                 -1.812
ZMB       -1.264         -1.170    -1.127                 -0.974
GHA       -1.306         -1.625    -1.174                 -0.191
ETH       -1.680         -1.293    -1.866                 -1.911
CMR       -1.724         -1.446    -1.790                 -2.005
DJI       -2.478         -2.831    -2.929                 -0.112
NER       -2.646         -4.775    -5.637                 -2.422
ZAF       -3.591         -2.684    -5.587                 -0.925
BFA       -5.302         -6.104    -7.953                 -5.836
SEN      -11.634        -10.257   -10.416                 -2.158
MLI      -39.023        -49.189   -36.429                -44.135
```


## Per-country MAE — geographic hold-out (sorted by XGBoost)

```
model    xgboost  random_forest  lightgbm  baseline_country_mean
Country                                                         
SDN         7.69           7.12      8.31                  18.50
KEN         5.57           5.53      5.68                   9.08
NGA         6.04           6.35      5.62                   7.72
SLV         5.25           5.74      5.29                   6.81
SOM         7.58           7.63      7.49                  10.31
YEM         9.50           9.48      9.74                  11.19
NAM        10.38           9.77     10.29                  12.62
AFG        10.15           9.64      9.84                  12.01
HTI         4.87           6.77      5.04                   5.24
TCD         5.99           5.86      5.90                   6.88
HND         5.81           5.08      5.67                   6.71
BGD         2.16           2.56      2.58                   4.33
GMB         6.49           5.61      6.88                   7.25
CAF        13.03          11.94     12.38                  14.62
COD         8.12           8.14      7.98                   8.64
ZWE         5.86           6.11      8.10                   6.95
GTM         5.97           5.89      5.94                   6.52
MOZ         8.23           8.54      8.33                   9.10
TGO         4.61           7.82      5.44                   4.90
MRT         6.68           8.24      7.27                   6.47
LBR         6.82           6.26      6.35                   6.92
GNB         3.74           3.45      3.82                   3.36
BEN         2.58           3.45      2.59                   2.28
GIN         4.74           5.15      4.56                   4.60
TLS         4.13           3.26      3.89                   2.76
PAK        10.87          10.46     11.33                  10.96
SSD        21.55          20.51     22.35                  19.61
CIV         2.91           2.73      3.11                   2.77
CPV         3.96           3.51      3.57                   2.98
ECU         3.66           2.66      4.73                   3.21
TZA        10.16          11.17     11.64                  11.12
ZMB         6.77           6.75      6.31                   6.67
GHA         4.36           4.50      4.30                   3.26
ETH         7.43           6.65      7.69                   7.65
CMR         4.54           4.89      5.04                   5.91
DJI        12.26          13.40     13.36                   7.85
NER         4.81           6.16      6.37                   4.73
ZAF         6.88           6.29      8.70                   4.50
BFA        25.03          26.82     30.61                  26.08
SEN         4.41           4.07      4.33                   2.22
MLI         5.72           6.90      5.63                   6.78
```
