# Nowcasting — findings (imputed)

Dataset: `merged_adm1_wide_norm_imputato_v3.parquet` | current windows: 4273 | with projections: 8197 (3924 projection). Drivers only. Baseline = persistence (carry last IPC forward).


## Rolling backtest — train_all | eval_current (PRIMARY)

```
   feature_set         model   MAE    R2  skill_vs_persistence
nowcast_change       xgboost 5.084 0.749                 0.178
       nowcast      lightgbm 5.132 0.745                 0.170
nowcast_change random_forest 5.167 0.745                 0.165
nowcast_change      lightgbm 5.099 0.744                 0.176
       nowcast       xgboost 5.232 0.742                 0.154
       nowcast random_forest 5.290 0.734                 0.145
autoregressive      lightgbm 5.783 0.697                 0.065
autoregressive random_forest 5.872 0.689                 0.051
autoregressive       xgboost 5.883 0.683                 0.049
autoregressive decision_tree 5.896 0.681                 0.047
nowcast_change decision_tree 6.050 0.665                 0.022
       nowcast decision_tree 6.106 0.642                 0.013
             -   persistence 6.185 0.625                 0.000
  drivers_only       xgboost 7.664 0.503                -0.239
  drivers_only      lightgbm 7.839 0.474                -0.267
  drivers_only random_forest 8.085 0.436                -0.307
  drivers_only decision_tree 9.658 0.192                -0.561
```


## Skill decomposition — autoregressive -> + driver levels -> + driver changes (R²)

```
        model  autoregressive_R2  nowcast_R2  nowcast_change_R2
      xgboost              0.683       0.742              0.749
random_forest              0.689       0.734              0.745
     lightgbm              0.697       0.745              0.744
decision_tree              0.681       0.642              0.665
```


Change-direction correlation (predicted vs actual change since last): r = 0.54.


## SHAP by data source (nowcast_change XGBoost)

```
persistence     11.681
rain             2.257
conflict         1.412
prices           1.356
vegetation       1.193
seasonality      0.968
displacement     0.764
media            0.762
```


## Localization — overall by scope (pooled over each scope's scored rows; `*_vs_global` = global model on those same rows)

```
                       n_rows  n_countries     R2   MAE  R2_vs_global  MAE_vs_global    dR2
scope                                                                                      
global                   1487           31  0.742  5.23           NaN            NaN    NaN
regional                 1487           31  0.734  5.26         0.742           5.23 -0.008
local                     810           10  0.649  5.37         0.638           5.41  0.012
cluster_kmeans           1478           31  0.751  5.16         0.744           5.21  0.007
cluster_hierarchical     1478           31  0.754  5.16         0.744           5.21  0.010
cluster_tfidf_kmeans     1457           30  0.660  5.56         0.725           5.21 -0.065
cluster_tfidf_hdbscan    1471           30  0.744  5.19         0.745           5.21 -0.001
cluster_emb_kmeans       1431           30  0.763  4.91         0.759           5.00  0.004
cluster_emb_hdbscan      1426           28  0.746  5.18         0.752           5.22 -0.006
```


## Localization — per country (regional beats global in 8/21; local beats global in 5/10; cluster_kmeans beats global in 11/21; cluster_hierarchical beats global in 9/21; cluster_tfidf_kmeans beats global in 6/20; cluster_tfidf_hdbscan beats global in 10/21; cluster_emb_kmeans beats global in 7/20; cluster_emb_hdbscan beats global in 8/20 countries (of those with that scope's model).)

```
         R2_global  R2_regional  R2_local  R2_cluster_kmeans  R2_cluster_hierarchical  R2_cluster_tfidf_kmeans  R2_cluster_tfidf_hdbscan  R2_cluster_emb_kmeans  R2_cluster_emb_hdbscan             best_scope
Country                                                                                                                                                                                                       
NGA          0.604        0.569     0.635              0.595                    0.547                    0.574                     0.574                  0.574                   0.574                  local
GIN          0.587        0.564       NaN              0.720                    0.660                    0.503                     0.503                  0.503                   0.503         cluster_kmeans
CMR          0.569        0.479       NaN              0.675                    0.674                    0.750                     0.750                  0.750                   0.750   cluster_tfidf_kmeans
CAF          0.540        0.296       NaN              0.485                    0.474                    0.260                     0.260                  0.417                   0.378                 global
SSD          0.526        0.644     0.586              0.638                    0.582                    0.501                     0.586                  0.576                   0.586               regional
MLI          0.498        0.689       NaN              0.505                    0.421                    0.678                     0.678                  0.678                   0.678               regional
COD          0.428        0.394     0.531              0.390                    0.428                    0.414                     0.414                  0.452                   0.519                  local
HND          0.311        0.404     0.191              0.130                    0.249                    0.392                     0.440                  0.252                   0.283  cluster_tfidf_hdbscan
TCD          0.295        0.008     0.027              0.160                    0.280                    0.014                     0.014                  0.014                   0.014                 global
GHA          0.276        0.444       NaN              0.305                    0.252                    0.420                     0.420                  0.420                   0.420               regional
SDN          0.228        0.305    -0.084              0.075                    0.105                    0.152                    -0.084                  0.040                   0.054               regional
YEM          0.218        0.204       NaN              0.265                    0.128                    0.032                     0.147                  0.192                   0.272    cluster_emb_hdbscan
NAM          0.158       -0.213       NaN              0.221                    0.245                   -0.056                    -0.066                    NaN                  -0.182   cluster_hierarchical
BEN          0.045        0.000       NaN             -0.065                   -0.071                   -0.018                    -0.018                 -0.018                  -0.018                 global
GTM         -0.098       -0.175    -0.128              0.070                    0.084                   -0.258                    -0.093                 -0.476                  -0.398   cluster_hierarchical
AFG         -0.196       -0.360    -0.353             -0.166                   -0.162                   -0.330                    -0.281                 -0.320                  -0.236   cluster_hierarchical
KEN         -0.237        0.138     0.277              0.050                    0.109                    0.311                     0.211                  0.351                   0.277     cluster_emb_kmeans
MOZ         -0.251       -0.488       NaN             -0.354                   -0.397                   -0.474                    -0.394                 -0.618                     NaN                 global
HTI         -0.292       -0.628       NaN             -0.882                   -0.794                      NaN                     0.038                 -0.433                  -0.534  cluster_tfidf_hdbscan
SOM         -0.401       -0.384    -0.303             -0.511                   -0.461                   -0.463                    -0.303                 -0.531                  -0.472                  local
MRT         -2.340       -0.386       NaN             -1.776                   -1.719                   -0.380                    -0.380                 -0.380                  -0.380   cluster_tfidf_kmeans
```
