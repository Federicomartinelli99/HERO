# Nowcasting IPC Phase 3+ — findings

panel_cur: 5054 windows | panel_all: 9596 windows (4542 projection). Temporal validation.

Persistence = carry last known IPC forward. Skill = MAE improvement over persistence.


## Rolling backtest — train_all | eval_current (PRIMARY)

```
  feature_set         model   MAE   RMSE    R2  skill_vs_persist
nowcast_delta       xgboost 5.202  7.968 0.693             0.170
      nowcast       xgboost 5.267  8.049 0.686             0.160
nowcast_delta      lightgbm 5.240  8.076 0.684             0.164
      nowcast      lightgbm 5.300  8.080 0.684             0.155
      nowcast random_forest 5.361  8.190 0.675             0.145
nowcast_delta random_forest 5.395  8.221 0.673             0.139
      ar_only       xgboost 5.642  8.347 0.663             0.100
      ar_only      lightgbm 5.585  8.374 0.660             0.109
      ar_only random_forest 5.657  8.428 0.656             0.098
      ar_only decision_tree 5.819  8.674 0.636             0.072
       static       xgboost 6.126  8.701 0.633             0.023
       static      lightgbm 6.286  8.839 0.622            -0.003
       static random_forest 6.483  9.002 0.608            -0.034
      nowcast decision_tree 6.344  9.453 0.567            -0.012
            -   persistence 6.269  9.568 0.557             0.000
nowcast_delta decision_tree 6.455  9.611 0.553            -0.030
       static decision_tree 7.496 10.425 0.474            -0.196
```


## Driver contribution — (AR + drivers) vs (AR only)

How much the exogenous drivers add on top of the autoregressive terms (lag1/lag2/trend/gap).

```
        model  ar_only_MAE  nowcast_MAE  nowcast_delta_MAE  levels_gain_pct  deltas_gain_pct  all_drivers_gain_pct  ar_only_R2  nowcast_R2  nowcast_delta_R2
      xgboost        5.642        5.267              5.202            0.067            0.012                 0.078       0.663       0.686             0.693
random_forest        5.657        5.361              5.395            0.052           -0.006                 0.046       0.656       0.675             0.673
     lightgbm        5.585        5.300              5.240            0.051            0.011                 0.062       0.660       0.684             0.684
decision_tree        5.819        6.344              6.455           -0.090           -0.017                -0.109       0.636       0.567             0.553
```


## Rolling backtest — train_cur | eval_current (exclude projections)

```
  feature_set         model   MAE   RMSE    R2  skill_vs_persist
      nowcast       xgboost 5.498  8.153 0.678             0.018
nowcast_delta       xgboost 5.528  8.270 0.669             0.013
      nowcast      lightgbm 5.498  8.296 0.667             0.018
nowcast_delta      lightgbm 5.546  8.336 0.664             0.009
      nowcast random_forest 5.480  8.367 0.661             0.021
nowcast_delta random_forest 5.541  8.409 0.658             0.010
            -   persistence 5.599  8.824 0.623             0.000
      ar_only random_forest 6.054  8.834 0.622            -0.081
      ar_only decision_tree 6.158  9.021 0.606            -0.100
       static       xgboost 6.529  9.196 0.591            -0.166
      nowcast decision_tree 6.126  9.222 0.588            -0.094
      ar_only      lightgbm 6.334  9.316 0.580            -0.131
      ar_only       xgboost 6.399  9.406 0.572            -0.143
       static      lightgbm 6.753  9.474 0.565            -0.206
       static random_forest 6.823  9.546 0.559            -0.219
nowcast_delta decision_tree 6.515  9.586 0.555            -0.164
       static decision_tree 8.193 11.458 0.364            -0.463
```


## Rolling backtest — train_all | eval_projection (reproducing IPC projections)

```
  feature_set         model   MAE   RMSE    R2  skill_vs_persist
nowcast_delta random_forest 3.833  5.411 0.886             0.181
nowcast_delta      lightgbm 3.990  5.473 0.884             0.147
nowcast_delta       xgboost 4.004  5.565 0.880             0.145
      nowcast       xgboost 4.159  5.744 0.872             0.111
      nowcast      lightgbm 4.244  5.795 0.870             0.093
      nowcast random_forest 4.169  5.837 0.868             0.109
            -   persistence 4.680  6.268 0.847             0.000
      ar_only random_forest 4.690  6.405 0.841            -0.002
      ar_only      lightgbm 4.674  6.407 0.841             0.001
      ar_only       xgboost 4.859  6.675 0.827            -0.038
nowcast_delta decision_tree 4.858  6.735 0.824            -0.038
      ar_only decision_tree 4.857  6.736 0.824            -0.038
      nowcast decision_tree 4.936  6.972 0.811            -0.055
       static       xgboost 7.751 10.113 0.603            -0.656
       static random_forest 7.806 10.312 0.587            -0.668
       static      lightgbm 8.067 10.542 0.568            -0.724
       static decision_tree 8.896 11.984 0.442            -0.901
```


## Headline holdout — train_all | eval_current

```
  feature_set         model   MAE   RMSE    R2  skill_vs_persist
      nowcast       xgboost 5.485  8.632 0.652             0.099
nowcast_delta       xgboost 5.491  8.686 0.648             0.098
      nowcast      lightgbm 5.503  8.712 0.645             0.096
nowcast_delta      lightgbm 5.466  8.719 0.645             0.102
      nowcast random_forest 5.551  8.737 0.643             0.088
nowcast_delta random_forest 5.627  8.858 0.634             0.075
      ar_only random_forest 5.855  8.953 0.626             0.038
      ar_only      lightgbm 5.849  8.960 0.625             0.039
      ar_only       xgboost 6.099  9.225 0.603            -0.002
      ar_only decision_tree 6.139  9.249 0.600            -0.009
            -   persistence 6.086  9.582 0.571             0.000
nowcast_delta decision_tree 6.556  9.964 0.536            -0.077
      nowcast decision_tree 6.656 10.013 0.532            -0.094
       static       xgboost 7.097 10.164 0.517            -0.166
       static      lightgbm 7.197 10.224 0.512            -0.183
       static random_forest 7.367 10.393 0.495            -0.211
       static decision_tree 8.304 11.665 0.364            -0.365
```


## Top nowcast drivers — mean(|SHAP|), XGBoost (panel_all)

```
lag1_phase3plus                            9.081
lag2_phase3plus                            1.477
d_rain_1m                                  1.081
is_projection                              0.871
Country                                    0.741
months_since_last                          0.605
idp_rate                                   0.416
d_rain_3m                                  0.382
month                                      0.340
year                                       0.322
wfp_price                                  0.284
rain_1m_sum                                0.279
acled_political_violence_events_per100k    0.266
rain_1m                                    0.263
recent_trend                               0.260
```


Change-direction correlation (predicted vs actual change since last assessment): r = 0.53.


## Per-country R2 — nowcast XGBoost vs persistence (train_all | eval_current)

```
model    xgboost  random_forest  lightgbm  persistence
Country                                               
MLI        0.733          0.716     0.694        0.455
CMR        0.637          0.714     0.562        0.282
SSD        0.518          0.563     0.566       -0.387
KEN        0.455          0.494     0.547       -0.123
CAF        0.406          0.440     0.387        0.231
GHA        0.374          0.442     0.401        0.006
HND        0.368          0.361     0.443       -0.427
GIN        0.236          0.220     0.152       -0.355
CIV        0.222          0.119     0.247        0.064
AFG        0.219          0.211     0.179       -0.118
NER        0.204          0.271     0.160       -0.417
COD        0.187          0.194     0.141        0.266
TCD        0.124          0.109     0.089       -1.207
TGO        0.121         -0.369     0.177       -1.690
SDN        0.053          0.106     0.129       -0.201
GMB       -0.038         -0.703    -0.137       -3.847
NGA       -0.094         -0.061    -0.049        0.308
SLE       -0.104         -0.368    -0.140       -1.125
NAM       -0.120         -0.116    -0.047       -0.054
CPV       -0.122         -0.313    -0.120       -1.094
GTM       -0.146          0.016    -0.035        0.063
BGD       -0.171          0.172     0.174       -1.088
GNB       -0.257         -0.480    -0.485       -2.197
TLS       -0.305          0.001    -0.283       -0.174
SOM       -0.344         -0.631    -0.307       -1.916
MOZ       -0.451         -0.384    -0.450       -0.296
LBR       -0.531         -3.544    -2.255       -5.072
ZMB       -0.562         -0.854    -0.615       -1.662
BEN       -0.650         -0.200    -0.552       -0.838
HTI       -0.845         -0.367    -0.979       -0.143
BFA       -1.098         -0.708    -0.792       -3.394
MRT       -1.112         -1.231    -0.943       -6.389
PAK       -1.272         -1.326    -0.791       -4.229
ECU       -1.423         -0.533    -1.307       -2.720
MDG       -2.003         -2.367    -1.974       -4.324
SEN       -6.010         -8.084    -4.074      -10.065
YEM       -6.335         -9.210    -8.311      -12.904
```


## Per-country MAE — nowcast XGBoost vs persistence (train_all | eval_current)

```
model    xgboost  random_forest  lightgbm  persistence
Country                                               
MLI         3.02           3.32      3.27         3.69
CMR         2.63           2.32      2.86         3.88
SSD         6.68           6.11      6.58        13.22
KEN         4.82           5.06      4.47         6.32
CAF         7.24           7.08      7.34         7.42
GHA         2.70           2.64      2.68         3.34
HND         5.26           5.51      5.10         7.59
GIN         3.71           3.79      4.07         4.45
CIV         2.41           2.66      2.40         2.27
AFG         5.95           5.87      6.00         6.65
NER         3.53           3.84      3.75         5.00
COD         4.75           4.87      5.30         4.82
TCD         4.61           4.61      4.73         6.64
TGO         2.49           3.44      2.42         4.05
SDN         9.39           9.03      8.96         9.94
GMB         3.77           4.87      3.94         8.19
NGA         5.49           5.21      5.44         5.46
SLE         3.96           4.41      3.97         5.00
NAM        12.71          12.65     12.53        12.18
CPV         2.53           2.73      2.50         3.48
GTM         5.10           4.55      4.95         4.52
BGD         6.81           5.57      5.51         9.58
GNB         2.43           2.56      2.47         3.07
TLS         8.91           7.98      8.98         8.08
SOM         5.37           6.07      5.39         7.70
MOZ         8.54           8.34      8.55         7.32
LBR         4.27           7.67      6.36         7.60
ZMB         9.26           9.92      9.15        11.33
BEN         2.67           2.37      2.59         3.00
HTI         7.36           6.37      7.88         6.09
BFA        10.17           9.09      9.40        13.17
MRT         4.35           4.45      4.17         8.09
PAK         3.50           3.61      3.21         4.57
ECU         5.90           4.76      5.97         7.91
MDG        11.01          11.68     10.99        13.67
SEN         3.71           4.50      3.28         3.71
YEM        15.71          18.90     17.15        17.15
```
