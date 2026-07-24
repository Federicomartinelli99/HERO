# Static inference — findings (imputed)

Dataset: `merged_adm1_wide_norm_imputato_v3.parquet` | rows=8457 | features=13 | target mean=23.6% | drivers only (no country, no coordinates)

Validation: GroupKFold(5) by area (out-of-fold) — test areas unseen.


## Model leaderboard (GroupKFold OOF)

```
                          MAE    RMSE     R2
baseline_country_mean   8.551  11.371  0.549
xgboost                 8.770  11.624  0.529
lightgbm                8.903  11.749  0.519
random_forest           9.105  12.144  0.486
decision_tree          10.564  14.178  0.299
```


## Top drivers — mean(|SHAP|), XGBoost

```
acled_political_violence_events_per_100k_population    2.856
wfp_price                                              2.771
idp_population_over_adm1_population                    2.560
month_cos                                              1.969
ndvi_vim                                               1.695
month_sin                                              1.411
wfp_inflation                                          1.272
ndvi_viq                                               1.176
gdelt_material_coop_events_per_100k_population         1.159
acled_total_fatalities_per_100k_population             1.025
rain_3m                                                1.018
gdelt_verbal_conflict_events_per_100k_population       0.988
rain_anomaly_3m                                        0.740
```


## SHAP by data source

```
prices          4.043
conflict        3.882
seasonality     3.380
vegetation      2.870
displacement    2.560
media           2.147
rain            1.758
```


## Localization — overall by scope (pooled over each scope's scored rows; `*_vs_global` = global model on those same rows)

```
                       n_rows  n_countries     R2   MAE  R2_vs_global  MAE_vs_global    dR2
scope                                                                                      
global                   8457           37  0.529  8.77           NaN            NaN    NaN
regional                 8407           35  0.617  7.64         0.529           8.77  0.088
local                    5469           11  0.589  7.91         0.445           9.39  0.144
cluster_kmeans           8415           37  0.527  8.66         0.529           8.78 -0.002
cluster_hierarchical     8415           37  0.538  8.51         0.529           8.78  0.009
cluster_tfidf_kmeans     8175           34  0.658  7.17         0.531           8.70  0.127
cluster_tfidf_hdbscan    8287           34  0.657  7.31         0.533           8.78  0.124
cluster_emb_kmeans       8371           35  0.646  7.36         0.532           8.77  0.114
cluster_emb_hdbscan      8148           34  0.657  7.30         0.531           8.81  0.126
```


## Localization — per country (regional beats global in 28/32; local beats global in 11/11; cluster_kmeans beats global in 18/33; cluster_hierarchical beats global in 17/33; cluster_tfidf_kmeans beats global in 29/30; cluster_tfidf_hdbscan beats global in 26/30; cluster_emb_kmeans beats global in 27/32; cluster_emb_hdbscan beats global in 28/31 countries (of those with that scope's model).)

```
         R2_global  R2_regional  R2_local  R2_cluster_kmeans  R2_cluster_hierarchical  R2_cluster_tfidf_kmeans  R2_cluster_tfidf_hdbscan  R2_cluster_emb_kmeans  R2_cluster_emb_hdbscan             best_scope
Country                                                                                                                                                                                                       
SDN          0.639        0.627     0.688              0.619                    0.665                    0.651                     0.688                  0.608                   0.657                  local
LBR          0.480        0.593       NaN              0.425                    0.453                    0.491                     0.491                  0.491                   0.491               regional
SWZ          0.420          NaN       NaN              0.261                    0.405                      NaN                     0.367                  0.343                   0.204                 global
CMR          0.327        0.023       NaN              0.366                    0.292                    0.458                     0.458                  0.458                   0.458   cluster_tfidf_kmeans
NAM          0.273        0.362       NaN              0.259                    0.392                    0.329                     0.336                  0.474                   0.455     cluster_emb_kmeans
TLS          0.266        0.489       NaN              0.510                    0.608                    0.403                     0.197                  0.449                   0.413   cluster_hierarchical
KEN          0.171        0.169     0.351              0.251                    0.241                    0.351                     0.224                  0.370                   0.351     cluster_emb_kmeans
AFG          0.133        0.164     0.198              0.134                    0.114                    0.154                     0.133                  0.175                   0.133                  local
ETH          0.035        0.161       NaN             -0.485                   -0.014                      NaN                       NaN                    NaN                   0.007               regional
TCD         -0.045        0.356     0.483             -0.042                    0.042                    0.331                     0.331                  0.331                   0.331                  local
SOM         -0.054       -0.031     0.235             -0.238                   -0.326                    0.100                     0.235                  0.075                   0.083                  local
SLV         -0.064       -0.162       NaN              0.205                    0.133                    0.196                     0.189                 -0.210                   0.393    cluster_emb_hdbscan
CAF         -0.067        0.068     0.088             -0.292                   -0.231                    0.103                     0.103                 -0.136                  -0.016   cluster_tfidf_kmeans
HND         -0.068        0.269     0.314              0.054                    0.016                    0.242                     0.233                  0.189                  -0.009                  local
COD         -0.107        0.083    -0.040             -0.204                   -0.211                    0.057                     0.057                 -0.087                  -0.043               regional
GTM         -0.166        0.068     0.218              0.083                    0.094                    0.263                     0.201                 -0.108                   0.198   cluster_tfidf_kmeans
MOZ         -0.229        0.141       NaN              0.084                   -0.060                    0.137                     0.220                  0.101                     NaN  cluster_tfidf_hdbscan
NGA         -0.327        0.213     0.318             -0.400                   -0.290                    0.232                     0.232                  0.232                   0.232                  local
NER         -0.425        0.197       NaN             -0.340                   -0.524                    0.191                     0.191                  0.191                   0.191               regional
GIN         -0.447        0.399       NaN             -0.330                   -0.828                    0.358                     0.358                  0.358                   0.358               regional
MRT         -0.500        0.287       NaN             -0.215                   -0.275                    0.303                     0.303                  0.303                   0.303   cluster_tfidf_kmeans
SLE         -0.504       -0.227       NaN             -0.098                   -0.143                   -0.134                    -0.134                 -0.134                  -0.134         cluster_kmeans
ZWE         -0.700       -0.172       NaN             -0.780                   -1.045                    0.138                       NaN                 -0.496                   0.228    cluster_emb_hdbscan
TGO         -0.705        0.462       NaN             -0.279                   -0.181                    0.506                     0.506                  0.506                   0.506   cluster_tfidf_kmeans
ECU         -0.747       -0.618       NaN             -1.762                   -1.144                   -8.167                    -1.278                 -1.234                     NaN               regional
SSD         -0.816       -0.512    -0.031             -0.352                   -0.467                   -0.002                    -0.031                 -0.061                  -0.031   cluster_tfidf_kmeans
BGD         -0.911       -0.051       NaN             -0.639                   -2.605                   -0.026                       NaN                 -0.193                  -0.061   cluster_tfidf_kmeans
MLI         -0.919        0.439       NaN             -3.246                   -2.140                    0.506                     0.506                  0.506                   0.506   cluster_tfidf_kmeans
YEM         -1.077        0.154       NaN             -1.106                   -0.223                    0.169                    -0.081                  0.118                   0.215    cluster_emb_hdbscan
BEN         -1.345        0.273       NaN             -0.887                   -0.656                    0.305                     0.305                  0.305                   0.305   cluster_tfidf_kmeans
HTI         -1.400       -0.583       NaN             -1.854                   -1.906                      NaN                    -0.656                 -0.532                   0.055    cluster_emb_hdbscan
GHA         -2.028        0.146       NaN             -1.609                   -1.448                    0.113                     0.113                  0.113                   0.113               regional
SEN         -2.805       -0.528       NaN             -3.737                   -4.515                   -0.677                    -0.677                 -0.677                  -0.677               regional
```
