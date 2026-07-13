# Analisi Integrata Sicurezza Alimentare (IPC)

Questo documento combina le analisi sviluppate nei 4 notebook di partenza, strutturando il codice per esplorare i dati del dataset `merged_adm1_wide.parquet`.

## 1. Caricamento Dati e Importazione Librerie

```python
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt

# Carico dataset merged_adm1_wide.parquet
df = pd.read_parquet("../../data/merged/merged_adm1_wide.parquet")
df
```

## 2. Andamento nel tempo (Aggregato Globale)
**Obiettivo:** Visualizzare le proporzioni delle fasi 3, 4 e 5 nel tempo tramite uno *Stacked Area Chart*.

```python
# 1. Forza la conversione della colonna temporale e normalizza il timestamp
df["From"] = pd.to_datetime(df["From"])
df["date_grouped"] = df["From"].dt.to_period("M").dt.to_timestamp()

# 2. Aggrega i dati nel tempo sommando i valori assoluti di tutti i paesi
df_time = (
    df.groupby("date_grouped")[
        ["phase_3_number", "phase_4_number", "phase_5_number"]
    ]
    .sum()
    .reset_index()
)

# 3. Calcola il totale complessivo delle tre fasi per determinare le proporzioni
total_vulnerable = (
    df_time["phase_3_number"]
    + df_time["phase_4_number"]
    + df_time["phase_5_number"]
)

# 4. Converti i valori assoluti in proporzioni percentuali relative
df_time["Fase 3 (%)"] = (df_time["phase_3_number"] / total_vulnerable) * 100
df_time["Fase 4 (%)"] = (df_time["phase_4_number"] / total_vulnerable) * 100
df_time["Fase 5 (%)"] = (df_time["phase_5_number"] / total_vulnerable) * 100

# 5. Imposta l'indice temporale per il plotting
df_plot = df_time.set_index("date_grouped")[
    ["Fase 3 (%)", "Fase 4 (%)", "Fase 5 (%)"]
]

# 6. Genera lo Stacked Area Chart con palette colore coerente al rischio
ax = df_plot.plot.area(
    figsize=(12, 6), color=["#fdb863", "#e66101", "#b2182b"], alpha=0.85
)

plt.title("Proporzione delle Fasi di Insicurezza Alimentare (IPC) nel Tempo")
plt.ylabel("Proporzione Relativa (%)")
plt.xlabel("Data di Inizio Analisi")
plt.ylim(0, 100)
plt.grid(True, linestyle="--", alpha=0.5)
plt.legend(loc="lower left")
plt.show()
```

## 3. Andamento di Fase 3+ nel Tempo per Singolo Paese
**Obiettivo:** Creare un grafico a linee interattivo (*Line Chart*) in Altair per osservare l'andamento della media di `phase_3plus_percentage` con menu a tendina.

```python
lista_paesi = df["Country"].unique().tolist()
lista_paesi.sort()

# 1. Normalizzazione temporale
df["From"] = pd.to_datetime(df["From"])
df["date_grouped"] = df["From"].dt.to_period("M").dt.to_timestamp()

# 2. Aggregazione: formato LONG richiesto da Altair
df_time = (
    df.groupby(["date_grouped", "Country"])["phase_3plus_percentage"]
    .mean()
    .reset_index()
)
seleziona_paese = alt.selection_point(fields=['Country'], bind=alt.binding_select(options=lista_paesi))

# 3. Generazione del grafico Altair
chart = alt.Chart(df_time).mark_line().encode(
    x=alt.X("date_grouped:T", title="Data di Inizio Analisi", scale=alt.Scale(domain=[df_time.date_grouped.min(), df_time.date_grouped.max()]),),
    y=alt.Y(
        "phase_3plus_percentage:Q",
        title="Fase 3+ (%)",
        scale=alt.Scale(domain=[0, 100]),
    ),
    color=alt.condition(seleziona_paese, alt.Color("Country:N", title="Paese", legend=None), alt.value("trasparent")),
    tooltip=[
        alt.Tooltip("Country:N", title="Paese"),
        alt.Tooltip("date_grouped:T", title="Data", format="%Y-%m"),
        alt.Tooltip("phase_3plus_percentage:Q", title="Fase 3+ (%)", format=".2f"),
    ],
).properties(
    width=800,
    height=400,
    title="Media di phase_3plus_percentage nel tempo per Paese"
).add_params(seleziona_paese)

chart.display()
```

## 4. Distribuzione 100% delle Fasi per Paese (Dati Attuali)
**Obiettivo:** Preparare i dati all'ultimo aggiornamento disponibile e visualizzare un grafico a barre orizzontali impilato e normalizzato al 100%.

```python
# Filtro dell'ultimo aggiornamento per ogni regione di ogni paese
ultimo_aggiornamento = df.groupby(['Country', 'adm1_pcode'])['From'].transform('max')

# Melt e Aggregazione per sommare i valori assoluti delle fasi
df_attuali = pd.melt(df[df["From"] == ultimo_aggiornamento], id_vars=['Country'], value_vars=['phase_3_number', 'phase_4_number', 'phase_5_number'])
df_chart = df_attuali.groupby(['Country', "variable"])['value'].sum().reset_index()

# Creazione del grafico normalizzato
chart = alt.Chart(df_chart).mark_bar().encode(
    x= alt.X("value:Q", stack='normalize'),
    y="Country:N",
    color="variable:N",
    tooltip=['Country', 'variable', 'value']
).properties(width=1000)

chart.display()
```

## 5. Totale Casi in Fase 3+ per Paese (Scala Trasformata)
**Obiettivo:** Sommare le fasi 3, 4 e 5 in un'unica variabile ("phase_3+"), ordinare i paesi per valore totale e applicare una scala a radice quadrata sull'asse X per migliorare la leggibilità delle differenze estreme.

```python
# Somma delle fasi critiche in una nuova colonna
ultimo_aggiornamento = df.groupby(['Country', 'adm1_pcode'])['From'].transform('max')
df["phase_3+"] = df["phase_3_number"] + df["phase_4_number"] + df["phase_5_number"]

# Preparazione formato per Altair
df_attuali = pd.melt(df[df["From"] == ultimo_aggiornamento], id_vars=['Country'], value_vars=['phase_3+'])
df_chart = df_attuali.groupby(['Country', "variable"])['value'].sum().reset_index()

# Grafico a barre con ordinamento decrescente e scala sqrt
chart = alt.Chart(df_chart).mark_bar().encode(
    x= alt.X("value:Q", scale=alt.Scale(type="sqrt")),
    y=alt.Y("Country:N", sort="-x"),
    color="variable:N",
    tooltip=['Country', 'variable', 'value']
).properties(width=1000)

chart.display()
```
