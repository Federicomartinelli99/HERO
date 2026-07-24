# Static inference — findings (unimputed)

Dataset: `merged_adm2_wide_norm.parquet` | rows=36938 | features=13 | target mean=22.5% | drivers only (no country, no coordinates)

Validation: GroupKFold(5) by area (out-of-fold) — test areas unseen.


## Model leaderboard (GroupKFold OOF)

```
                         MAE    RMSE     R2
random_forest          8.722  12.062  0.610
xgboost                9.055  12.342  0.592
lightgbm               9.200  12.450  0.585
baseline_country_mean  9.430  12.862  0.557
decision_tree          9.729  13.573  0.506
```


## Top drivers — mean(|SHAP|), XGBoost

```
month_sin                                              3.752
idp_population_over_adm1_population                    3.728
month_cos                                              2.451
ndvi_viq                                               2.287
acled_political_violence_events_per_100k_population    2.186
rain_3m                                                2.024
ndvi_vim                                               1.051
wfp_inflation                                          0.743
wfp_price                                              0.663
rain_anomaly_3m                                        0.602
acled_total_fatalities_per_100k_population             0.475
gdelt_material_coop_events_per_100k_population         0.392
gdelt_verbal_conflict_events_per_100k_population       0.340
```


## SHAP by data source

```
seasonality     6.203
displacement    3.728
vegetation      3.338
conflict        2.661
rain            2.625
prices          1.406
media           0.731
```


## Localization — overall by scope (pooled over each scope's scored rows; `*_vs_global` = global model on those same rows)

```
                       n_rows  n_countries     R2   MAE  R2_vs_global  MAE_vs_global    dR2
scope                                                                                      
global                  36938           38  0.592  9.06           NaN            NaN    NaN
regional                35903           33  0.673  7.88         0.596           9.05  0.077
local                   35980           24  0.696  7.46         0.601           8.98  0.095
cluster_kmeans          33080           26  0.664  8.21         0.615           8.94  0.049
cluster_hierarchical    33080           26  0.673  8.08         0.615           8.94  0.059
cluster_tfidf_kmeans    36825           34  0.683  7.78         0.594           9.01  0.089
cluster_tfidf_hdbscan   36696           36  0.683  7.76         0.594           9.05  0.089
cluster_emb_kmeans      36906           37  0.672  7.89         0.592           9.06  0.080
cluster_emb_hdbscan     36894           36  0.676  7.78         0.592           9.05  0.083
```


## Localization — per country (regional beats global in 25/27; local beats global in 24/24; cluster_kmeans beats global in 20/23; cluster_hierarchical beats global in 20/23; cluster_tfidf_kmeans beats global in 28/29; cluster_tfidf_hdbscan beats global in 28/29; cluster_emb_kmeans beats global in 28/31; cluster_emb_hdbscan beats global in 28/31 countries (of those with that scope's model).)

```
         R2_global  R2_regional  R2_local  R2_cluster_kmeans  R2_cluster_hierarchical  R2_cluster_tfidf_kmeans  R2_cluster_tfidf_hdbscan  R2_cluster_emb_kmeans  R2_cluster_emb_hdbscan             best_scope
Country                                                                                                                                                                                                       
CMR          0.388        0.485     0.490              0.429                    0.405                    0.454                     0.454                  0.454                   0.454                  local
MWI          0.339          NaN     0.533                NaN                      NaN                    0.431                     0.485                  0.395                   0.489                  local
NGA          0.290        0.398     0.433              0.348                    0.367                    0.393                     0.393                  0.393                   0.393                  local
BFA          0.274        0.291     0.387             -1.957                   -1.987                    0.319                     0.319                  0.319                   0.319                  local
SDN          0.222        0.339     0.373              0.289                    0.336                    0.360                     0.373                  0.370                   0.374    cluster_emb_hdbscan
MOZ          0.161        0.331     0.384              0.325                    0.256                    0.344                     0.382                  0.333                   0.384                  local
YEM          0.115        0.366     0.395              0.238                    0.315                    0.363                     0.380                  0.334                   0.364                  local
COD          0.091        0.175     0.190              0.199                    0.194                    0.174                     0.183                  0.079                   0.165         cluster_kmeans
SSD          0.039        0.214     0.246              0.238                    0.215                    0.261                     0.246                  0.236                   0.231   cluster_tfidf_kmeans
LBN          0.038          NaN       NaN                NaN                      NaN                    0.323                     0.203                  0.020                   0.291   cluster_tfidf_kmeans
CAF         -0.019        0.106     0.032              0.055                    0.083                    0.056                     0.061                  0.037                   0.012               regional
ZMB         -0.023        0.276     0.254                NaN                      NaN                    0.259                     0.294                  0.248                   0.228  cluster_tfidf_hdbscan
ETH         -0.047       -0.320     0.494             -0.182                   -0.007                    0.453                     0.429                  0.499                   0.458     cluster_emb_kmeans
PSE         -0.048          NaN       NaN                NaN                      NaN                      NaN                     0.101                  0.126                  -0.368     cluster_emb_kmeans
TCD         -0.110        0.217     0.325              0.044                    0.163                    0.185                     0.185                  0.185                   0.185                  local
ZWE         -0.157        0.060     0.141              0.063                   -0.006                    0.144                     0.150                  0.120                   0.109  cluster_tfidf_hdbscan
PAK         -0.181        0.218     0.095             -0.070                   -0.136                    0.095                     0.224                  0.146                   0.095  cluster_tfidf_hdbscan
MDG         -0.258       -0.127       NaN                NaN                      NaN                   -0.527                    -1.727                 -0.483                  -0.392               regional
MRT         -0.301        0.244     0.301             -0.192                    0.067                    0.247                     0.247                  0.247                   0.247                  local
GHA         -0.345       -0.058    -0.102             -0.027                   -0.012                   -0.040                    -0.040                 -0.040                  -0.040   cluster_hierarchical
MLI         -0.365       -0.054     0.106             -1.516                   -1.180                    0.017                     0.017                  0.017                   0.017                  local
BGD         -0.391        0.011       NaN             -0.357                   -0.140                    0.213                       NaN                  0.076                   0.177   cluster_tfidf_kmeans
SOM         -0.398       -1.276       NaN                NaN                      NaN                      NaN                       NaN                 -0.248                  -0.909     cluster_emb_kmeans
NER         -0.420        0.198     0.300             -0.213                    0.211                    0.232                     0.232                  0.232                   0.232                  local
UGA         -0.428        0.230     0.378                NaN                      NaN                    0.245                     0.234                  0.073                   0.378                  local
TGO         -0.570       -0.054     0.252              0.013                    0.008                   -0.014                    -0.014                 -0.014                  -0.014                  local
GIN         -0.580       -0.165    -0.031             -0.177                   -0.221                   -0.146                    -0.146                 -0.146                  -0.146                  local
SEN         -0.588       -0.229    -0.051             -0.574                   -0.716                   -0.195                    -0.195                 -0.195                  -0.195                  local
SLE         -0.659       -0.430       NaN             -0.489                   -0.584                   -0.407                    -0.407                 -0.407                  -0.407   cluster_tfidf_kmeans
BEN         -1.408       -0.261     0.175             -0.379                   -0.306                   -0.249                    -0.249                 -0.249                  -0.249                  local
AGO         -2.651          NaN       NaN                NaN                      NaN                   -0.568                    -0.700                 -1.379                  -1.120   cluster_tfidf_kmeans
```
