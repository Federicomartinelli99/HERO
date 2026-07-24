# Text-narrative cluster membership

Reference for the four **text-narrative** localization scopes used in the static-inference and nowcast
rounds (and inherited at admin-2). They come from the colleague's unsupervised clustering of each **IPC
report's narrative** — a TF-IDF and a dense-embedding representation, each split by **K-Means** and
**HDBSCAN** — so there are four schemes in total.

**How the label is assigned.** The source rows are per *(country, analysis-period)*. Each country is
collapsed to **one static label = the mode across its periods** (HDBSCAN noise, `-1`, dropped first),
then joined to every admin-1/2 area of that country. So each country sits **wholly in one cluster**, and
the grouping is a stable, ex-ante country attribute (like `region`) — not time-varying.

**Coverage.** The text corpus overlaps **23 of 37** modelled countries. The **14** countries with no
IPC-report text (the West-Africa/Sahel block) share one **catch-all `OTHER`** group in every scheme, so
each scope still covers 100% of rows — see the note at the end.

> Themes are the cluster's representative label (embedding) or top keywords (TF-IDF); read them as a
> rough gloss, not a definition. `n` = number of *modelled* countries in the cluster.

## Embedding · K-Means — `cluster_emb_kmeans`

Dense-embedding representation of each IPC report, K-Means. The most balanced and interpretable text
scheme.

| cluster | n | theme | countries |
|---|---|---|---|
| 0 | 3 | Malnutrizione Infantile (child malnutrition) | MOZ (Mozambique), PAK (Pakistan), SOM (Somalia) |
| 2 | 2 | Impatto Precipitazioni sui Raccolti (rainfall impact on crops) | NAM (Namibia), SWZ (Eswatini) |
| 3 | 2 | Impatto Economico COVID-19 (COVID economic impact) | ETH (Ethiopia), ZAF (South Africa) |
| 4 | 4 | Emergenza Rifugiati da Conflitto (conflict-refugee emergency) | AFG (Afghanistan), COD (DR Congo), SSD (South Sudan), YEM (Yemen) |
| 5 | 4 | Vulnerabilità Idrica Agropastorale (agropastoral water vulnerability) | KEN (Kenya), SDN (Sudan), TLS (Timor-Leste), ZWE (Zimbabwe) |
| 6 | 8 | Inflazione Prezzi Agricoli (agricultural price inflation) | AGO (Angola), BGD (Bangladesh), CAF (Central African Republic), ECU (Ecuador), GTM (Guatemala), HND (Honduras), HTI (Haiti), SLV (El Salvador) |

## Embedding · HDBSCAN — `cluster_emb_hdbscan`

Dense-embedding representation, HDBSCAN (density-based; carves off several singletons).

| cluster | n | theme | countries |
|---|---|---|---|
| 0 | 1 | Impatto El Niño e La Niña | ECU (Ecuador) |
| 2 | 1 | Malattie del Bestiame (livestock disease) | KEN (Kenya) |
| 3 | 2 | Stress Economico Generalizzato (generalized economic stress) | SDN (Sudan), ZWE (Zimbabwe) |
| 4 | 5 | Impatto Pandemia COVID-19 | ETH (Ethiopia), GTM (Guatemala), SLV (El Salvador), SWZ (Eswatini), ZAF (South Africa) |
| 5 | 2 | Shock Climatico Agricolo (agricultural climate shock) | NAM (Namibia), TLS (Timor-Leste) |
| 6 | 1 | Inondazioni e Monsoni (floods and monsoon) | PAK (Pakistan) |
| 7 | 1 | Malnutrizione Infantile (child malnutrition) | MOZ (Mozambique) |
| 8 | 1 | Crisi Umanitaria da Conflitto (humanitarian conflict crisis) | SSD (South Sudan) |
| 9 | 2 | — (no dominant label) | COD (DR Congo), YEM (Yemen) |
| 10 | 7 | Tendenze Macroeconomiche (macroeconomic trends) | AFG (Afghanistan), AGO (Angola), BGD (Bangladesh), CAF (Central African Republic), HND (Honduras), HTI (Haiti), SOM (Somalia) |

## TF-IDF · K-Means — `cluster_tfidf_kmeans`

TF-IDF bag-of-words representation, K-Means. Themes are the cluster's top keywords.

| cluster | n | theme | countries |
|---|---|---|---|
| 0 | 1 | price, dry spell, livelihood acute, production | ETH (Ethiopia) |
| 1 | 5 | price, production, water, market, stock, livestock, rainfall, lean | AGO (Angola), BGD (Bangladesh), MOZ (Mozambique), SDN (Sudan), ZWE (Zimbabwe) |
| 2 | 5 | food security, price, shock, security situation, urgent, improvement | AFG (Afghanistan), NAM (Namibia), PAK (Pakistan), TLS (Timor-Leste), ZAF (South Africa) |
| 5 | 3 | humanitarian assistance, food security, update | ECU (Ecuador), SSD (South Sudan), YEM (Yemen) |
| 6 | 3 | grain, coffee, basic grain, department, reserve, price | GTM (Guatemala), HND (Honduras), SLV (El Salvador) |
| 7 | 2 | conflict, humanitarian, assistance, improvement, crisis | HTI (Haiti), SWZ (Eswatini) |
| 8 | 2 | refugee, armed conflict, host, group, displacement | CAF (Central African Republic), COD (DR Congo) |
| 9 | 2 | food security, rain, livestock, rainfall, nutrition, assessment | KEN (Kenya), SOM (Somalia) |

## TF-IDF · HDBSCAN — `cluster_tfidf_hdbscan`

TF-IDF representation, HDBSCAN (one large generic bucket + singletons).

| cluster | n | theme | countries |
|---|---|---|---|
| 1 | 1 | livelihood acute, dry spell, gap livelihood, high acute | ETH (Ethiopia) |
| 2 | 2 | armed conflict, host, prefecture, territory, armed group, idp | CAF (Central African Republic), COD (DR Congo) |
| 3 | 1 | bad acute, population bad, county, people acute | SSD (South Sudan) |
| 4 | 1 | water, animal, access food, locality, market, cereal | SDN (Sudan) |
| 5 | 1 | security nutrition, nutrition, humanitarian, humanitarian assistance | SOM (Somalia) |
| 6 | 10 | people population, high acute, population high, humanitarian | AFG (Afghanistan), ECU (Ecuador), HTI (Haiti), KEN (Kenya), NAM (Namibia), PAK (Pakistan), SWZ (Eswatini), TLS (Timor-Leste), YEM (Yemen), ZAF (South Africa) |
| 7 | 1 | livestock, market, income, dry, food stock, meal, maize | ZWE (Zimbabwe) |
| 9 | 1 | disaster, nutritional, deficit, vulnerable, proportion | BGD (Bangladesh) |
| 10 | 5 | basic grain, coffee, income, reserve, department, strategy | AGO (Angola), GTM (Guatemala), HND (Honduras), MOZ (Mozambique), SLV (El Salvador) |

## `OTHER` — shared catch-all (identical in all four schemes)

Modelled countries absent from the IPC-report text corpus, pooled into one group so the text scopes cover
every row. **This bucket reflects *absence of text*, not a narrative type** — a deliberate hybrid so the
scope is comparable head-to-head with `global`/`regional` on the same rows.

**14 countries:** BEN (Benin), BFA (Burkina Faso), CMR (Cameroon), GHA (Ghana), GIN (Guinea),
LBR (Liberia), MLI (Mali), MRT (Mauritania), NER (Niger), NGA (Nigeria), SEN (Senegal),
SLE (Sierra Leone), TCD (Chad), TGO (Togo).

## Caveats

- **Country granularity.** Each country is wholly in one cluster, so these scopes group *countries*
  (coarser than the per-admin-1 driver-fingerprint clusters) — closer in spirit to `regional`.
- **HDBSCAN fragmentation.** HDBSCAN produces several singleton clusters (one country = effectively its
  own model); the tiniest don't clear the fit floor and fall back to global for that scope.
- **Static vs nowcast.** These groupings lift the static "why" model materially (+0.11–0.13 ΔR² at
  admin-1) but are a wash for the nowcast — see the localization sections of
  [overview_static_inference.md](overview_static_inference.md), [overview_nowcast.md](overview_nowcast.md)
  and [overview_admin2.md](overview_admin2.md).
