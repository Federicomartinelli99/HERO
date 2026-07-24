# Nowcasting — findings (unimputed)

Dataset: `merged_adm2_wide_norm.parquet` | current windows: 19716 | with projections: 35851 (16135 projection). Drivers only. Baseline = persistence (carry last IPC forward).


## Rolling backtest — train_all | eval_current (PRIMARY)

```
   feature_set         model   MAE    R2  skill_vs_persistence
nowcast_change       xgboost 5.929 0.698                 0.185
nowcast_change      lightgbm 5.988 0.694                 0.176
nowcast_change random_forest 6.061 0.685                 0.166
       nowcast       xgboost 6.024 0.681                 0.171
       nowcast      lightgbm 6.031 0.679                 0.170
       nowcast random_forest 6.274 0.662                 0.137
autoregressive      lightgbm 6.634 0.617                 0.088
autoregressive       xgboost 6.672 0.614                 0.082
autoregressive decision_tree 6.759 0.612                 0.070
autoregressive random_forest 6.780 0.607                 0.068
nowcast_change decision_tree 7.057 0.590                 0.029
       nowcast decision_tree 7.196 0.578                 0.010
             -   persistence 7.271 0.517                 0.000
  drivers_only       xgboost 8.628 0.463                -0.187
  drivers_only      lightgbm 8.672 0.462                -0.193
  drivers_only random_forest 8.498 0.454                -0.169
  drivers_only decision_tree 9.462 0.283                -0.301
```


## Skill decomposition — autoregressive -> + driver levels -> + driver changes (R²)

```
        model  autoregressive_R2  nowcast_R2  nowcast_change_R2
      xgboost              0.614       0.681              0.698
random_forest              0.607       0.662              0.685
     lightgbm              0.617       0.679              0.694
decision_tree              0.612       0.578              0.590
```


Change-direction correlation (predicted vs actual change since last): r = 0.55.


## SHAP by data source (nowcast_change XGBoost)

```
persistence     12.225
rain             2.753
seasonality      1.808
vegetation       1.519
displacement     1.047
conflict         1.024
prices           0.459
media            0.343
```


## Localization — overall by scope (pooled over each scope's scored rows; `*_vs_global` = global model on those same rows)

```
                       n_rows  n_countries     R2   MAE  R2_vs_global  MAE_vs_global    dR2
scope                                                                                      
global                   8093           33  0.681  6.02           NaN            NaN    NaN
regional                 7896           28  0.705  5.85         0.704           5.88  0.001
local                    7826           22  0.700  5.89         0.705           5.89 -0.005
cluster_kmeans           7312           22  0.728  5.67         0.738           5.59 -0.010
cluster_hierarchical     7312           22  0.726  5.71         0.738           5.59 -0.013
cluster_tfidf_kmeans     8064           30  0.686  5.98         0.696           5.93 -0.010
cluster_tfidf_hdbscan    8022           31  0.671  6.07         0.684           6.01 -0.013
cluster_emb_kmeans       8085           32  0.664  6.11         0.681           6.02 -0.017
cluster_emb_hdbscan      8083           31  0.673  6.00         0.681           6.02 -0.008
```


## Localization — per country (regional beats global in 14/23; local beats global in 10/22; cluster_kmeans beats global in 9/20; cluster_hierarchical beats global in 10/20; cluster_tfidf_kmeans beats global in 15/25; cluster_tfidf_hdbscan beats global in 13/24; cluster_emb_kmeans beats global in 13/25; cluster_emb_hdbscan beats global in 16/25 countries (of those with that scope's model).)

```
         R2_global  R2_regional  R2_local  R2_cluster_kmeans  R2_cluster_hierarchical  R2_cluster_tfidf_kmeans  R2_cluster_tfidf_hdbscan  R2_cluster_emb_kmeans  R2_cluster_emb_hdbscan            best_scope
Country                                                                                                                                                                                                      
BFA          0.559        0.590     0.376                NaN                      NaN                    0.576                     0.576                  0.576                   0.576              regional
MLI          0.514        0.637     0.675              0.365                    0.503                    0.609                     0.609                  0.609                   0.609                 local
SSD          0.448        0.372     0.352              0.395                    0.388                    0.393                     0.352                  0.390                   0.369                global
NGA          0.429        0.463     0.449              0.406                    0.431                    0.423                     0.423                  0.423                   0.423              regional
CMR          0.398        0.442     0.514              0.436                    0.387                    0.525                     0.525                  0.525                   0.525  cluster_tfidf_kmeans
COD          0.264        0.181     0.239              0.206                    0.205                    0.155                     0.176                  0.174                   0.262                global
UGA          0.190       -0.547    -0.274                NaN                      NaN                   -0.295                    -0.369                 -0.491                  -0.274                global
CAF          0.182        0.126    -0.056              0.151                    0.132                    0.125                     0.090                 -0.052                  -0.052                global
GHA         -0.041        0.049    -0.108             -0.177                   -0.164                    0.066                     0.066                  0.066                   0.066  cluster_tfidf_kmeans
TCD         -0.042       -0.140    -0.220             -0.097                   -0.016                   -0.109                    -0.109                 -0.109                  -0.109  cluster_hierarchical
SDN         -0.071       -0.340    -0.415             -0.165                   -0.268                   -0.386                    -0.415                 -0.553                  -0.391                global
LBN         -0.108          NaN       NaN                NaN                      NaN                    0.048                    -0.312                 -0.280                  -0.042  cluster_tfidf_kmeans
NER         -0.204        0.195     0.209             -0.113                   -0.075                    0.128                     0.128                  0.128                   0.128                 local
YEM         -0.220       -0.545    -0.375             -0.240                   -0.155                   -0.671                    -0.275                 -0.610                  -0.122   cluster_emb_hdbscan
MWI         -0.265          NaN    -0.400                NaN                      NaN                   -0.334                    -0.267                 -0.405                  -0.593                global
SLE         -0.293        0.002       NaN             -0.219                   -0.078                    0.027                     0.027                  0.027                   0.027  cluster_tfidf_kmeans
SEN         -0.407       -0.199    -0.095             -0.156                   -0.301                   -0.137                    -0.137                 -0.137                  -0.137                 local
TGO         -0.489       -0.053    -0.529             -0.223                   -0.215                   -0.023                    -0.023                 -0.023                  -0.023  cluster_tfidf_kmeans
BEN         -0.491       -0.431    -0.730             -0.425                   -0.382                   -0.352                    -0.352                 -0.352                  -0.352  cluster_tfidf_kmeans
ZMB         -0.681       -0.113    -0.312                NaN                      NaN                   -0.670                    -0.641                 -0.709                  -0.521              regional
MOZ         -0.721       -0.162    -0.228             -0.162                   -0.484                   -0.295                    -0.235                 -0.139                  -0.228    cluster_emb_kmeans
GIN         -1.291       -0.734    -0.323             -0.607                   -0.491                   -0.602                    -0.602                 -0.602                  -0.602                 local
PAK         -1.369       -1.984    -1.313             -1.229                   -1.447                   -1.537                    -2.951                 -1.016                  -1.313    cluster_emb_kmeans
MRT         -1.752       -0.377    -0.252             -3.744                   -3.147                   -0.334                    -0.334                 -0.334                  -0.334                 local
BGD         -1.992       -4.092       NaN             -2.003                   -2.353                   -1.847                       NaN                 -2.204                  -2.365  cluster_tfidf_kmeans
```
