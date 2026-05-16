try:
    # import pandera as pa
    # from pandera import Column, DataFrameSchema, Check
    WFPDataSchema = None
    # # Schema per validare il file Parquet caricato (Data Contract)
    # WFPDataSchema = DataFrameSchema(
    #     {
    #         "ISO3": Column(str, Check.str_length(3, 3), coerce=True),
    #         "country": Column(str, coerce=True),
    #         "date": Column("datetime64[ns]", coerce=True),
    #         "adm1_name": Column(str, nullable=True, coerce=True),
    #         "inflation_food_price_index": Column(float, nullable=True, coerce=True),
    #     },
    #     strict=False, # strict=False permette alle commodity (es. wheat) di esistere dinamicamente
    #     name="WFP_Consolidated_Schema"
    # )
except ImportError:
    print("Pandera non installato. Validazione schema saltata (pip install pandera).")
    print("Oppure Pandera funziona solo su sistemi linux")
    WFPDataSchema = None # Graceful fallback se Pandera non è installato
