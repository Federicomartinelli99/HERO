# Static inference — findings (unimputed)

Dataset: `merged_adm1_wide_norm_v3.parquet` | rows=8457 | features=13 | target mean=23.6% | drivers only (no country, no coordinates)

Validation: GroupKFold(5) by area (out-of-fold) — test areas unseen.


## Model leaderboard (GroupKFold OOF)

```
                          MAE    RMSE     R2
baseline_country_mean   8.551  11.371  0.549
xgboost                 8.890  11.614  0.530
lightgbm                8.989  11.720  0.521
random_forest           9.059  11.911  0.505
decision_tree          10.294  13.697  0.346
```


## Top drivers — mean(|SHAP|), XGBoost

```
idp_population_over_adm1_population                    4.341
acled_political_violence_events_per_100k_population    2.043
wfp_price                                              1.824
month_cos                                              1.497
ndvi_vim                                               1.464
rain_3m                                                1.452
month_sin                                              1.341
wfp_inflation                                          1.338
acled_total_fatalities_per_100k_population             1.286
gdelt_verbal_conflict_events_per_100k_population       1.014
ndvi_viq                                               0.980
gdelt_material_coop_events_per_100k_population         0.933
rain_anomaly_3m                                        0.706
```


## SHAP by data source

```
displacement    4.341
conflict        3.329
prices          3.163
seasonality     2.838
vegetation      2.444
rain            2.158
media           1.947
```


## Localization — overall by scope (pooled over each scope's scored rows; `*_vs_global` = global model on those same rows)

```
                       n_rows  n_countries     R2   MAE  R2_vs_global  MAE_vs_global    dR2
scope                                                                                      
global                   8457           37  0.530  8.89           NaN            NaN    NaN
regional                 8407           35  0.615  7.82         0.534           8.86  0.081
local                    5469           11  0.567  8.17         0.469           9.24  0.097
cluster_kmeans           8415           37  0.510  8.95         0.530           8.90 -0.020
cluster_hierarchical     8415           37  0.532  8.76         0.530           8.90  0.002
cluster_tfidf_kmeans     8175           34  0.624  7.68         0.530           8.85  0.094
cluster_tfidf_hdbscan    8287           34  0.641  7.59         0.536           8.88  0.105
cluster_emb_kmeans       8371           35  0.638  7.59         0.533           8.89  0.105
cluster_emb_hdbscan      8148           34  0.637  7.66         0.535           8.90  0.103
```


## Localization — per country (regional beats global in 24/32; local beats global in 11/11; cluster_kmeans beats global in 17/33; cluster_hierarchical beats global in 18/33; cluster_tfidf_kmeans beats global in 23/30; cluster_tfidf_hdbscan beats global in 23/30; cluster_emb_kmeans beats global in 27/32; cluster_emb_hdbscan beats global in 28/31 countries (of those with that scope's model).)

```
         R2_global  R2_regional  R2_local  R2_cluster_kmeans  R2_cluster_hierarchical  R2_cluster_tfidf_kmeans  R2_cluster_tfidf_hdbscan  R2_cluster_emb_kmeans  R2_cluster_emb_hdbscan             best_scope
Country                                                                                                                                                                                                       
SDN          0.619        0.614     0.687              0.581                    0.687                    0.652                     0.687                  0.627                   0.657                  local
KEN          0.235        0.140     0.279              0.328                    0.233                    0.242                     0.231                  0.257                   0.279         cluster_kmeans
NAM          0.122        0.118       NaN              0.105                    0.223                    0.008                     0.204                  0.189                   0.156   cluster_hierarchical
AFG          0.107        0.159     0.166              0.140                    0.143                    0.158                     0.137                  0.149                   0.137                  local
SOM          0.012        0.105     0.245             -0.176                   -0.256                    0.178                     0.245                  0.138                   0.135                  local
LBR          0.002       -0.011       NaN             -0.053                   -0.111                   -0.087                    -0.087                 -0.087                  -0.087                 global
COD          0.002        0.116     0.031             -0.086                   -0.083                   -0.065                    -0.065                  0.001                   0.008               regional
TLS         -0.061       -0.049       NaN             -0.126                    0.003                   -0.134                     0.120                 -0.049                   0.041  cluster_tfidf_hdbscan
ETH         -0.098       -0.378       NaN             -0.286                   -0.105                      NaN                       NaN                    NaN                   0.164    cluster_emb_hdbscan
GTM         -0.155       -0.303    -0.059             -0.207                   -0.226                   -0.374                    -0.317                 -0.245                  -0.345                  local
TCD         -0.162        0.178     0.378             -0.104                   -0.022                    0.171                     0.171                  0.171                   0.171                  local
CAF         -0.239        0.040    -0.036             -0.275                   -0.163                   -0.059                    -0.059                  0.113                  -0.093     cluster_emb_kmeans
MRT         -0.280        0.066       NaN             -0.175                   -0.564                    0.077                     0.077                  0.077                   0.077   cluster_tfidf_kmeans
SSD         -0.357       -0.188    -0.008             -0.316                   -0.298                   -0.016                    -0.008                 -0.003                  -0.008     cluster_emb_kmeans
MOZ         -0.360        0.183       NaN             -0.067                   -0.260                    0.302                     0.254                  0.056                     NaN   cluster_tfidf_kmeans
ECU         -0.466       -0.591       NaN             -0.668                   -0.746                   -0.241                    -0.796                 -2.058                     NaN   cluster_tfidf_kmeans
SLE         -0.477       -0.712       NaN             -0.397                   -0.661                   -0.742                    -0.742                 -0.742                  -0.742         cluster_kmeans
HND         -0.503       -0.226    -0.101             -0.564                   -0.553                   -0.304                    -0.316                 -0.274                   0.015    cluster_emb_hdbscan
SWZ         -0.536          NaN       NaN             -0.530                   -0.529                      NaN                    -0.025                  0.283                  -0.116     cluster_emb_kmeans
NGA         -0.543        0.272     0.357             -0.933                   -0.698                    0.280                     0.280                  0.280                   0.280                  local
SLV         -0.576       -0.572       NaN             -0.491                   -0.264                   -0.830                    -0.787                 -0.569                  -0.192    cluster_emb_hdbscan
CMR         -0.621       -0.167       NaN             -0.159                   -0.366                    0.558                     0.558                  0.558                   0.558   cluster_tfidf_kmeans
HTI         -0.649        0.366       NaN             -1.245                   -0.943                      NaN                     0.515                  0.426                   0.341  cluster_tfidf_hdbscan
GIN         -0.660       -0.089       NaN             -0.321                   -0.651                    0.039                     0.039                  0.039                   0.039   cluster_tfidf_kmeans
NER         -0.691       -0.139       NaN             -0.659                   -0.912                    0.004                     0.004                  0.004                   0.004   cluster_tfidf_kmeans
YEM         -0.883        0.201       NaN             -1.179                   -0.196                    0.218                     0.261                  0.183                   0.247  cluster_tfidf_hdbscan
TGO         -1.374       -0.223       NaN             -0.747                   -0.772                   -0.120                    -0.120                 -0.120                  -0.120   cluster_tfidf_kmeans
BGD         -1.518        0.252       NaN             -0.706                   -1.353                    0.170                       NaN                  0.240                   0.166               regional
ZWE         -1.673       -0.096       NaN             -1.125                   -1.395                   -0.002                       NaN                  0.159                   0.099     cluster_emb_kmeans
GHA         -1.836       -0.396       NaN             -1.759                   -1.571                   -0.224                    -0.224                 -0.224                  -0.224   cluster_tfidf_kmeans
MLI         -1.838        0.036       NaN             -3.782                   -2.546                    0.139                     0.139                  0.139                   0.139   cluster_tfidf_kmeans
SEN         -2.055       -0.566       NaN             -2.802                   -2.379                   -0.453                    -0.453                 -0.453                  -0.453   cluster_tfidf_kmeans
BEN         -2.862       -0.038       NaN             -1.794                   -1.961                   -0.163                    -0.163                 -0.163                  -0.163               regional
```
