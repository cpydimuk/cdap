# Design Spec — PySpark Supply Chain Optimization Model

Companion to `REQUIREMENTS.md`. That document defines *what* and *why*;
this one defines *how*.

## 1. Approach at a Glance

The system is a four-stage pipeline over Spark DataFrames:

```
                 ┌────────────────────┐
                 │  Synthetic Data     │
                 │  Generator          │
                 └──────────┬──────────┘
                            │  products, locations, lanes,
                            │  capacities, demand_history
                            ▼
                 ┌────────────────────┐
                 │ 1. Demand           │
                 │    Forecasting      │
                 └──────────┬──────────┘
                            │  forecast(product, location, period,
                            │           qty, uncertainty)
              ┌─────────────┴─────────────┐
              ▼                           ▼
   ┌────────────────────┐      ┌────────────────────┐
   │ 2. Inventory        │      │ 3. Network /        │
   │    Optimization     │      │    Distribution     │
   │    (safety stock,   │      │    Optimization     │
   │     ROP, order-up-to│      │    (shipment plan)  │
   └──────────┬──────────┘      └──────────┬──────────┘
              │                            │
              └─────────────┬──────────────┘
                            ▼
                 ┌────────────────────┐
                 │ 4. Production /     │
                 │    Procurement      │
                 │    Planning         │
                 └──────────┬──────────┘
                            ▼
                 ┌────────────────────┐
                 │  Pipeline Outputs   │
                 │  + run metadata     │
                 └────────────────────┘
```

Forecasting output is the shared input to inventory optimization and to
network optimization. Inventory policy (target stock levels) becomes a
demand-side input to production/procurement planning; network flow
becomes its supply-side input. All four stages exchange data exclusively
through Parquet artifacts with fixed schemas — no stage imports another
stage's internals — so any stage can be swapped or run standalone.

## 2. Key Design Decisions

### 2.1 Why PySpark for optimization, not just for ETL

Spark has no native distributed LP/MIP solver. The design uses Spark for
what it's good at — data prep, feature engineering, and **embarrassingly
parallel optimization** — and delegates the actual solving to a
single-node solver library invoked once per independent sub-problem:

- **Forecasting** is naturally parallel across `(product, location)`
  series: grouped with `groupBy(...).applyInPandas(...)`, each group
  fit independently on an executor.
- **Network optimization** is solved **per product (or per product
  family)** as an independent LP, because in this design lanes and
  capacities are product-family-scoped and products don't compete for
  the same unit of capacity across families. Each sub-problem is small
  enough to solve with a single-node solver inside a
  `applyInPandas`/`mapInPandas` call, distributed across the cluster the
  same way as forecasting.
- **Inventory optimization** is a closed-form/analytic computation per
  `(product, location)` (safety stock formulas), so it is a plain
  vectorized Spark transformation — no external solver needed.
- **Production/procurement** is solved per plant/product-family for the
  same reason as network optimization.

This keeps every optimization call inside a bounded, single-node problem
size that off-the-shelf solvers handle in milliseconds-to-seconds, while
Spark provides the distribution across the (potentially large) number of
independent sub-problems. It avoids depending on a distributed
commercial solver (Gurobi/CPLEX distributed mode) that may not be
available in every environment.

If a scenario has **cross-family shared capacity** (a real constraint in
some networks), the corresponding sub-problems are grouped by whatever
key actually shares that capacity — the partitioning key is a config
concern, not a code-structure one.

### 2.2 Sequential vs. joint solve of network + production/procurement

**Decision: sequential, with one feedback pass.**

1. Network optimization first solves flow assuming production/supplier
   capacity is as given in `production_capacity` /
   `supplier_capacity` (i.e., an upper bound, not yet allocated).
2. Production/procurement planning then solves make/buy quantities to
   satisfy the network's required plant output, respecting the same
   capacity tables.
3. If production/procurement optimization reports infeasibility (e.g., a
   plant can't produce what the network plan asked for), the reported
   binding constraints are fed back as a tightened capacity input and
   network optimization is re-solved once.

This is simpler to implement, test, and distribute than a joint
MIP across both stages, at the cost of potential (small) sub-optimality
when capacity is tightly binding. A fully joint formulation is noted as
a Phase 2 extension in §8. This tradeoff is called out explicitly because
it was flagged as an open question in `REQUIREMENTS.md` §8 — confirm
before implementation if joint solving is actually required for the
target use case.

### 2.3 Forecasting model choice

**Decision: pluggable, with two built-in implementations selected by
config (`forecast.model: naive_seasonal | gbt`).**

- `naive_seasonal` — seasonal-naive / moving-average baseline (no ML
  dependency), always available, used as the correctness/sanity
  baseline and in fast test runs.
- `gbt` — gradient-boosted trees (Spark MLlib `GBTRegressor`) over
  lag and calendar features, one model per `(product, location)` group
  (or per product family if data is too sparse per series — configurable
  grouping key).

Both implement the same interface (`Forecaster.fit_predict(history_df,
horizon) -> forecast_df`), so adding a third model later (e.g., Prophet
via a pandas UDF) doesn't touch pipeline code.

### 2.4 Solver library

**Decision: OR-Tools' linear solver (CBC/GLOP backend) via a thin
wrapper**, because it's Apache-2.0 licensed, has no external binary
dependency beyond the pip package, and handles both LP (network flow)
and MIP (if integer shipment batches / minimum order quantities are
turned on) with the same API. PuLP is kept as a documented fallback
behind the same wrapper interface, in case OR-Tools is unavailable in a
target environment (this is called out as an assumption in
`REQUIREMENTS.md` §8).

### 2.5 Where this project lives / how it runs

**Decision: standalone top-level project, not a CDAP application.**

This repository is the CDAP platform itself; `cdap-spark-python` exists
to let *CDAP pipeline programs* call into Python/PySpark, not to host
general-purpose PySpark applications. Coupling this model to CDAP's
Java application lifecycle would add significant complexity
(CDAP app/plugin packaging, artifact deployment, CDAP's program
lifecycle APIs) with no requirement calling for it today.

Instead, this lives as its own top-level directory
(`pyspark-supply-chain-optimizer/`), packaged as a normal Python
project and runnable directly with `spark-submit` or
`python -m supply_chain.pipeline.run`, following the same
already-established pattern as `dataplex-mcp-server/` in this repo
(self-contained Python project, own `pyproject.toml`, own `docs/`).
If there's a future need to run this *as* a CDAP pipeline stage, the
core library (pure functions operating on DataFrames, no CLI/IO
assumptions baked in) can be wrapped in a CDAP Spark program at that
time without modification — the design deliberately keeps "business
logic" and "CLI/orchestration" in separate modules (§3) to keep that
door open.

## 3. Project Layout

```
pyspark-supply-chain-optimizer/
├── pyproject.toml
├── README.md
├── docs/
│   ├── REQUIREMENTS.md
│   └── DESIGN.md
├── config/
│   └── default_scenario.yaml
├── src/
│   └── supply_chain/
│       ├── __init__.py
│       ├── config.py              # config load + validation (FR-7)
│       ├── spark_session.py       # local/cluster SparkSession factory
│       ├── datagen/
│       │   ├── generator.py       # FR-1: products/locations/lanes/capacity/demand_history
│       │   └── schemas.py         # StructType definitions, one per table
│       ├── forecasting/
│       │   ├── base.py            # Forecaster interface
│       │   ├── naive_seasonal.py
│       │   ├── gbt.py
│       │   └── metrics.py         # MAPE/WMAPE/RMSE
│       ├── inventory/
│       │   └── policy.py          # safety stock, ROP, order-up-to (FR-3)
│       ├── network/
│       │   ├── model.py           # LP formulation (decision vars, constraints)
│       │   └── solve.py           # applyInPandas driver, per-group solve
│       ├── production/
│       │   ├── model.py           # make/buy LP/MIP formulation
│       │   └── solve.py
│       ├── solvers/
│       │   └── ortools_lp.py      # thin solver wrapper (shared by network + production)
│       ├── pipeline/
│       │   ├── run.py             # FR-6: end-to-end orchestration entry point
│       │   └── io.py              # read/write artifacts, path abstraction
│       └── reporting/
│           └── run_summary.py     # FR-6.3: metadata, accuracy, cost, feasibility summary
├── tests/
│   ├── unit/                      # one test module per src/ module above
│   └── integration/
│       └── test_pipeline_end_to_end.py   # small fixed scenario, local Spark
└── notebooks/                     # optional exploratory analysis, not part of the pipeline
```

## 4. Data Schemas (Phase 1, synthetic)

All schemas are defined once in `datagen/schemas.py` as Spark
`StructType`s and reused by every stage (both to generate and to
validate). Summary:

**`products`**
`product_id: string, family_id: string, unit_cost: double, unit_volume: double`

**`locations`**
`location_id: string, type: string [plant|dc|demand_point], region: string, throughput_capacity: double`

**`lanes`**
`source_id: string, dest_id: string, family_id: string, unit_cost: double, capacity_per_period: double, transit_time_periods: int`

**`production_capacity`**
`plant_id: string, family_id: string, period: int, capacity: double, unit_cost: double`

**`supplier_capacity`**
`supplier_id: string, family_id: string, period: int, capacity: double, unit_cost: double, min_order_qty: double`

**`demand_history`**
`product_id: string, location_id: string, period: int, demand: double`

**Stage output schemas:**

- `forecast`: `product_id, location_id, period, forecast_qty, forecast_std`
- `inventory_policy`: `product_id, location_id, safety_stock, reorder_point, order_up_to_level, holding_cost`
- `shipment_plan`: `source_id, dest_id, product_id, period, quantity, cost`
- `production_plan`: `plant_id, product_id, period, make_qty, buy_qty, supplier_id, cost`
- `feasibility_report`: `stage, constraint, entity_id, period, shortfall, message`

## 5. Module Interfaces (contracts between stages)

Every stage module exposes one pure function taking and returning Spark
DataFrames, so stages are independently testable with small in-memory
DataFrames and no filesystem I/O:

```python
def forecast(history: DataFrame, config: ForecastConfig) -> DataFrame: ...

def compute_inventory_policy(forecast: DataFrame, lead_times: DataFrame,
                              config: InventoryConfig) -> DataFrame: ...

def optimize_network(forecast: DataFrame, lanes: DataFrame,
                      locations: DataFrame, config: NetworkConfig
                      ) -> tuple[DataFrame, DataFrame]:  # (shipment_plan, feasibility_report)
    ...

def optimize_production(shipment_plan: DataFrame, production_capacity: DataFrame,
                         supplier_capacity: DataFrame, config: ProductionConfig
                         ) -> tuple[DataFrame, DataFrame]:  # (production_plan, feasibility_report)
    ...
```

`pipeline/run.py` is the only module that sequences these calls and
handles reading/writing artifacts between them (FR-6.2: each stage
remains independently runnable by pointing it at a previous stage's
written output instead of an in-memory DataFrame).

## 6. Distributed Optimization Pattern (detail)

For network optimization (§2.1), the Spark-side driver looks like:

```python
def solve_group(pdf: pd.DataFrame) -> pd.DataFrame:
    # pdf = all lanes + demand rows for one family_id
    problem = build_lp(pdf)          # network/model.py
    solution = solve(problem)        # solvers/ortools_lp.py
    return solution_to_frame(solution)

shipment_plan = (
    joined_df
    .groupBy("family_id")
    .applyInPandas(solve_group, schema=SHIPMENT_PLAN_SCHEMA)
)
```

This is the same pattern used for forecasting and production
optimization, just with a different group key and a different
single-node function. Group sizes are bounded by scenario design
(a family's lanes + locations), keeping each `applyInPandas` call
well within single-executor memory.

## 7. Testing Strategy

- **Unit tests**: one test module per stage, using small hand-built
  DataFrames (a handful of products/locations) with known correct
  answers (e.g., a safety-stock formula checked against a manual
  calculation; a 2-node network LP checked against an obvious optimal
  solution).
- **Integration test**: generate a small fixed synthetic scenario (seeded),
  run `pipeline/run.py` end-to-end in local Spark mode, and assert:
  outputs exist with expected schemas, no unhandled infeasibility,
  and basic consistency checks (e.g., sum of shipments to a location
  ≈ its forecast within the policy buffer).
- All tests run against local Spark (`master=local[2]`) so CI needs no
  cluster.

## 8. Future Extensions (explicitly out of scope now)

- Joint (rather than sequential) network + production/procurement
  optimization for tightly capacity-constrained scenarios.
- Real data connectors (warehouse tables, ERP extracts) implementing the
  same schemas as the synthetic generator, so downstream stages don't
  change.
- Stochastic evaluation / backtesting of resulting policies via
  simulation.
- Optional CDAP Spark-program wrapper (see §2.5) if this needs to run as
  a CDAP pipeline stage.
- Multi-objective optimization (cost vs. service level vs. carbon) if
  needed later.

## 9. Summary of Decisions Needing Your Sign-off

Before coding starts, please confirm or redirect:

1. **Sequential network → production/procurement solve** (§2.2), not joint.
2. **OR-Tools as the solver**, PuLP as documented fallback (§2.4).
3. **Standalone top-level project**, not CDAP-integrated (§2.5).
4. **Grouping key for distributed solves is `family_id`** by default,
   configurable (§2.1) — confirm this matches how capacity is actually
   shared in the scenarios you care about.
5. **Synthetic data only for Phase 1** (per your answer) — real
   connectors are future work (§8), not blocking.
