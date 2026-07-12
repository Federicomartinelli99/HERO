# FASE 2: Approccio Statico (Cross-Sectional, Senza Sequenzialità)

Tratta i dati collassando l'asse temporale, considerando ogni osservazione (regione in un determinato periodo) come un record indipendente ("cross-section").

---

## Task 2.1 - Clustering dei Paesi (EDA Statica)
* **Algoritmi**: K-Means, DBSCAN, Hierarchical Clustering.
* **Metodologia**: Calcolo dei valori medi storici standardizzati di tutti i driver per ciascun paese.
* **Visualizzazione**: Creazione di Heatmap ordinate e dendrogrammi per raggruppare i paesi in base alla pura magnitudo delle loro crisi (es. "Paesi a forte intensità di conflitto" vs "Paesi a forte vulnerabilità climatica").

---

## Task 2.2 - Inferenza su IPC in base alle Features Correnti
* **Target**: Stima della percentuale di popolazione in crisi alimentare (`phase_3plus_percentage`).
* **Modelli**: K-Nearest Neighbors (KNN), Decision Trees, Support Vector Machines (SVM), Random Forest, XGBoost.
* **Explainability**: Utilizzo dei plot di **Feature Importance** e **SHAP (SHapley Additive exPlanations)** per identificar e classificare quali driver esogeni (es. inflazione alimentare vs numero conflitti) esercitino il massimo impatto predittivo in logica statica.
* **Rilevanza delle Coordinate**: Inclusione di `latitude` e `longitude` standardizzate come feature. Tramite SHAP, si quantificherà l'importanza relativa dello spazio geografico rispetto alle variabili socio-economiche e di conflitto.

---

## 📊 Grafici e Visualizzazioni per la FASE 2
* **Dendrogramma Gerarchico Statico**: Grafico ad albero per mostrare la gerarchia di aggregazione dei paesi basata sulle medie dei driver.
* **Heatmap dei Cluster statici**: Una matrice ordinata secondo i cluster ottenuti, con i driver sulle colonne e i paesi sulle righe, colorata in base alla magnitudo normalizzata del driver (per identificare a colpo d'occhio i fattori dominanti di ciascun cluster).
* **SHAP Summary Plot (Beeswarm)**: Grafico che mostra l'impatto positivo o negativo di ciascuna feature sulla predizione dell'IPC3+, con i punti colorati in base al valore alto/basso della feature. Evidenzierà visivamente la rilevanza relativa di `latitude` e `longitude` rispetto ai driver socio-economici.
* **Scatter Plot 2D (PCA / t-SNE)**: Rappresentazione bidimensionale dei cluster statici di paesi, colorati per etichetta di cluster, per valutare la separabilità geometrica nello spazio ridotto.
