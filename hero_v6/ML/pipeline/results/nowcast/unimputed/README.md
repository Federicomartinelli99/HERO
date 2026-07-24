# Nowcasting — findings (unimputed)

Dataset: `merged_adm1_wide_norm_v3.parquet` | current windows: 4273 | with projections: 8197 (3924 projection). Drivers only. Baseline = persistence (carry last IPC forward).


## Rolling backtest — train_all | eval_current (PRIMARY)

```
   feature_set         model   MAE    R2  skill_vs_persistence
nowcast_change      lightgbm 5.299 0.740                 0.143
nowcast_change       xgboost 5.324 0.738                 0.139
nowcast_change random_forest 5.395 0.734                 0.128
       nowcast       xgboost 5.432 0.731                 0.122
       nowcast      lightgbm 5.476 0.726                 0.115
       nowcast random_forest 5.469 0.725                 0.116
autoregressive      lightgbm 5.778 0.698                 0.066
autoregressive random_forest 5.872 0.689                 0.051
autoregressive       xgboost 5.883 0.683                 0.049
autoregressive decision_tree 5.896 0.681                 0.047
nowcast_change decision_tree 6.269 0.655                -0.014
       nowcast decision_tree 6.186 0.647                -0.000
             -   persistence 6.185 0.625                 0.000
  drivers_only       xgboost 8.084 0.463                -0.307
  drivers_only      lightgbm 8.164 0.452                -0.320
  drivers_only random_forest 8.513 0.403                -0.376
  drivers_only decision_tree 9.719 0.170                -0.571
```


## Skill decomposition — autoregressive -> + driver levels -> + driver changes (R²)

```
        model  autoregressive_R2  nowcast_R2  nowcast_change_R2
      xgboost              0.683       0.731              0.738
random_forest              0.689       0.725              0.734
     lightgbm              0.698       0.726              0.740
decision_tree              0.681       0.647              0.655
```


Change-direction correlation (predicted vs actual change since last): r = 0.52.


## SHAP by data source (nowcast_change XGBoost)

```
persistence     11.561
rain             2.475
vegetation       1.250
seasonality      1.084
conflict         1.041
prices           1.030
media            0.946
displacement     0.657
```


## Localization — overall by scope (pooled over each scope's scored rows; `*_vs_global` = global model on those same rows)

```
                       n_rows  n_countries     R2   MAE  R2_vs_global  MAE_vs_global    dR2
scope                                                                                      
global                   1487           31  0.731  5.43           NaN            NaN    NaN
regional                 1487           31  0.724  5.45         0.731           5.43 -0.006
local                     810           10  0.629  5.67         0.655           5.38 -0.026
cluster_kmeans           1478           31  0.727  5.51         0.733           5.41 -0.007
cluster_hierarchical     1478           31  0.730  5.46         0.733           5.41 -0.003
cluster_tfidf_kmeans     1457           30  0.674  5.73         0.713           5.42 -0.038
cluster_tfidf_hdbscan    1471           30  0.728  5.46         0.734           5.42 -0.006
cluster_emb_kmeans       1431           30  0.752  5.21         0.755           5.15 -0.003
cluster_emb_hdbscan      1426           28  0.716  5.58         0.742           5.41 -0.026
```


## Localization — per country (regional beats global in 10/21; local beats global in 4/10; cluster_kmeans beats global in 8/21; cluster_hierarchical beats global in 10/21; cluster_tfidf_kmeans beats global in 8/20; cluster_tfidf_hdbscan beats global in 11/21; cluster_emb_kmeans beats global in 9/20; cluster_emb_hdbscan beats global in 8/20 countries (of those with that scope's model).)

```
         R2_global  R2_regional  R2_local  R2_cluster_kmeans  R2_cluster_hierarchical  R2_cluster_tfidf_kmeans  R2_cluster_tfidf_hdbscan  R2_cluster_emb_kmeans  R2_cluster_emb_hdbscan             best_scope
Country                                                                                                                                                                                                       
NGA          0.610        0.555     0.602              0.538                    0.380                    0.523                     0.523                  0.523                   0.523                 global
SSD          0.601        0.619     0.579              0.643                    0.585                    0.506                     0.579                  0.498                   0.579         cluster_kmeans
MLI          0.581        0.645       NaN              0.544                    0.489                    0.628                     0.628                  0.628                   0.628               regional
CMR          0.580        0.669       NaN              0.525                    0.564                    0.758                     0.758                  0.758                   0.758   cluster_tfidf_kmeans
CAF          0.392        0.362       NaN              0.394                    0.404                    0.279                     0.279                  0.289                   0.325   cluster_hierarchical
HND          0.369        0.284     0.182              0.327                    0.257                    0.333                     0.370                  0.388                   0.274     cluster_emb_kmeans
YEM          0.288        0.376       NaN              0.257                    0.090                    0.107                     0.358                  0.202                   0.128               regional
COD          0.261        0.339     0.383              0.256                    0.387                    0.370                     0.370                  0.336                   0.362   cluster_hierarchical
GIN          0.254        0.040       NaN              0.296                    0.255                    0.087                     0.087                  0.087                   0.087         cluster_kmeans
SDN          0.241        0.241    -0.067              0.126                    0.076                    0.083                    -0.067                  0.055                  -0.037                 global
TCD          0.099       -0.040    -0.115              0.108                    0.094                   -0.068                    -0.068                 -0.068                  -0.068         cluster_kmeans
KEN          0.069        0.259     0.244              0.108                    0.218                    0.235                     0.071                  0.445                   0.244     cluster_emb_kmeans
GHA          0.061        0.129       NaN             -0.036                   -0.029                    0.185                     0.185                  0.185                   0.185   cluster_tfidf_kmeans
NAM         -0.027       -0.415       NaN             -0.008                    0.016                   -0.210                    -0.118                    NaN                  -0.466   cluster_hierarchical
AFG         -0.064       -0.302    -0.463             -0.035                    0.006                   -0.394                    -0.304                 -0.362                  -0.348   cluster_hierarchical
MOZ         -0.263       -0.442       NaN             -0.255                   -0.250                   -0.281                    -0.502                 -0.594                     NaN   cluster_hierarchical
HTI         -0.276       -0.417       NaN             -0.756                   -0.924                      NaN                     0.074                 -0.463                  -0.583  cluster_tfidf_hdbscan
GTM         -0.354       -0.203    -0.154             -0.359                   -0.292                   -0.155                    -0.208                 -0.171                  -0.177                  local
BEN         -0.395       -0.654       NaN             -0.494                   -0.550                   -0.804                    -0.804                 -0.804                  -0.804                 global
SOM         -0.576       -0.377    -0.260             -0.726                   -0.472                   -0.353                    -0.260                 -0.306                  -0.342                  local
MRT         -2.147       -0.583       NaN             -2.486                   -2.022                   -0.520                    -0.520                 -0.520                  -0.520   cluster_tfidf_kmeans
```
