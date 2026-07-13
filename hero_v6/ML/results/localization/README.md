# Localization — does localizing the model help?

For each country, R² under three training scopes (XGBoost). Static = GroupKFold by area; Nowcast = rolling-origin backtest.


## Static

Regional beats global in **33/47** countries; local beats global in **26/33** (of those with a local model).

```
         R2_global  R2_regional  R2_local best_scope
Country                                             
SDN          0.686        0.722     0.699   regional
YEM          0.477        0.639     0.548   regional
NGA          0.448        0.476     0.638      local
KEN          0.291        0.298     0.289   regional
NAM          0.251        0.392     0.465      local
SWZ          0.250          NaN       NaN     global
CMR          0.233        0.429     0.655      local
ZMB          0.227        0.248    -0.022   regional
AFG          0.191        0.247     0.319      local
SLV          0.182        0.312     0.331      local
ZWE          0.181        0.138       NaN     global
MLI          0.173        0.289     0.331      local
MOZ          0.163        0.226     0.136   regional
SOM          0.120        0.243     0.221   regional
GMB          0.114        0.311     0.334      local
NER          0.105        0.341     0.420      local
CAF          0.039        0.148     0.071   regional
ETH          0.021       -0.019    -0.564     global
MRT          0.016        0.259     0.339      local
LSO          0.005          NaN       NaN     global
TLS          0.000       -0.073       NaN     global
COD         -0.028        0.114     0.098   regional
GTM         -0.043       -0.156    -0.013      local
LBR         -0.053       -0.104     0.026      local
TCD         -0.057        0.345     0.410      local
SLE         -0.084       -0.163       NaN     global
GHA         -0.108        0.010    -0.170   regional
MDG         -0.125       -0.036       NaN   regional
CPV         -0.149       -0.115    -0.309   regional
GNB         -0.177       -0.433     0.121      local
CIV         -0.183       -0.160    -0.241   regional
HND         -0.211       -0.087     0.234      local
GIN         -0.226        0.115     0.216      local
PAK         -0.238       -0.347       NaN     global
BGD         -0.295        0.060    -0.067   regional
SSD         -0.322       -0.360    -0.050      local
HTI         -0.473       -0.381     0.487      local
TGO         -0.624       -0.513    -0.566   regional
ECU         -0.696       -0.248       NaN   regional
SEN         -0.791       -0.367    -0.404   regional
BEN         -1.174       -0.288     0.242      local
ZAF         -1.243       -0.332       NaN   regional
UGA         -1.266       -4.123       NaN     global
BFA         -2.153       -1.307       NaN   regional
DJI         -2.636       -1.236       NaN   regional
AGO         -3.686          NaN       NaN     global
BDI        -32.585          NaN       NaN     global
```


## Nowcast

Regional beats global in **22/37** countries; local beats global in **10/31** (of those with a local model).

```
         R2_global  R2_regional  R2_local best_scope
Country                                             
MLI          0.733        0.675     0.692     global
CMR          0.637        0.772     0.764   regional
SSD          0.518        0.565     0.453   regional
KEN          0.455        0.252     0.206     global
CAF          0.406        0.265     0.203     global
GHA          0.374        0.313     0.025     global
HND          0.368        0.391     0.238   regional
GIN          0.236        0.165    -0.110     global
CIV          0.222        0.233     0.174   regional
AFG          0.219       -0.221    -0.194     global
NER          0.204        0.238     0.092   regional
COD          0.187        0.485     0.185   regional
TCD          0.124        0.055     0.157      local
TGO          0.121        0.207    -0.762   regional
SDN          0.053       -0.052     0.145      local
GMB         -0.038        0.007    -2.292   regional
NGA         -0.094       -0.256    -0.014      local
SLE         -0.104        0.194    -2.241   regional
NAM         -0.120       -0.175    -0.558     global
CPV         -0.122       -0.067    -0.538   regional
GTM         -0.146        0.004     0.113      local
BGD         -0.171        0.197       NaN   regional
GNB         -0.257       -0.302    -0.666     global
TLS         -0.305        0.014       NaN   regional
SOM         -0.344       -0.702    -0.286      local
MOZ         -0.451       -0.277    -0.224      local
LBR         -0.531       -0.094    -1.413   regional
ZMB         -0.562       -0.689    -1.302     global
BEN         -0.650       -0.221    -0.953   regional
HTI         -0.845       -0.042    -0.202   regional
BFA         -1.098       -1.234       NaN     global
MRT         -1.112       -0.422    -0.944   regional
PAK         -1.272       -1.084       NaN   regional
ECU         -1.423        0.219       NaN   regional
MDG         -2.003       -1.779       NaN   regional
SEN         -6.010       -3.896    -6.766   regional
YEM         -6.335       -6.870    -0.918      local
```
