# Requirements Document — PySpark Supply Chain Optimization Model

## 1. Purpose

Build a PySpark-based system that helps a manufacturing/distribution
organization decide, on a recurring planning cycle:

1. **How much demand to expect**, per product and location, over the
   planning horizon.
2. **How much inventory to hold and when to reorder it**, per product and
   location, to hit a target service level at minimum cost.
3. **Which plants/warehouses should serve which downstream locations, and
   how goods should flow between them**, at minimum transportation cost
   and within capacity limits.
4. **How much to produce or procure, where, and when**, subject to
   production/supplier capacity, to meet the plan at minimum cost.

These four problems are solved as a chained pipeline: forecasting output
feeds the three optimization stages, and the optimization stages share a
common network/capacity model.

## 2. Scope

### 2.1 In scope

- A synthetic data generator that produces a self-consistent supply chain
  scenario (products, locations, network, costs, capacities, historical
  demand) so the model is runnable and testable without an external data
  source.
- Demand forecasting per (product, location) time series.
- Multi-echelon inventory optimization (safety stock, reorder point,
  order-up-to level) driven by forecast uncertainty and service-level
  targets.
- Network/distribution optimization: sourcing assignment and shipment
  quantities across a plant → DC → destination network, minimizing
  transportation + handling cost subject to capacity and demand
  satisfaction.
- Production/procurement planning: make/buy quantities and timing per
  plant/supplier, subject to capacity and cost, consistent with the
  network plan.
- A pipeline orchestration layer that runs the four stages in order,
  passing data between them as Spark DataFrames / Parquet artifacts.
- Config-driven scenario parameters (scenario size, service levels, cost
  assumptions, planning horizon).
- Unit and integration tests runnable on a small synthetic scenario
  without a cluster (local Spark).

### 2.2 Out of scope (for this phase)

- Real-time/streaming demand sensing.
- Connectors to production data warehouses (BigQuery, Snowflake, ERP
  systems) — the interface is designed to make adding these later
  straightforward, but none is implemented now.
- A UI/dashboard. Outputs are Parquet/CSV tables plus optional plots in
  notebooks.
- Deep integration with CDAP's Java runtime (CDAP application/plugin
  packaging). See `DESIGN.md` §7 for how this stays an option later.
- Stochastic/simulation-based evaluation of the resulting policies
  (e.g., Monte Carlo backtesting) — noted as a future extension.

## 3. Primary Use Cases

| # | Use case | Actor | Outcome |
|---|----------|-------|---------|
| UC1 | Generate a synthetic scenario | Analyst/developer | Reproducible input dataset of a given size |
| UC2 | Forecast demand for the next N periods | Planner | Per-SKU/location forecast + uncertainty band |
| UC3 | Compute inventory policies | Planner | Safety stock, reorder point, order-up-to level per SKU/location |
| UC4 | Optimize network flow | Planner | Shipment plan (source → destination, quantity) minimizing cost, respecting capacity |
| UC5 | Optimize production/procurement | Planner | Make/buy quantities and timing per plant/supplier |
| UC6 | Run the full pipeline end-to-end | Planner/automation | A complete, internally consistent supply plan for the horizon |
| UC7 | Re-run with changed assumptions | Analyst | Compare scenarios (e.g., service level 95% vs 98%, capacity −10%) |

## 4. Functional Requirements

### FR-1 Data generation
- FR-1.1 Generate `products`, `locations` (plants, DCs, stores/customers),
  `lanes` (allowed source→destination pairs with cost, capacity, transit
  time), `production_capacity`, `supplier_capacity`, and `demand_history`
  tables.
- FR-1.2 All generation must be seedable for reproducibility.
- FR-1.3 Scenario size (number of products, locations, history length)
  must be configurable.
- FR-1.4 Generated data must be internally consistent (e.g., every demand
  record references a valid product/location; every lane references
  valid locations).

### FR-2 Demand forecasting
- FR-2.1 Produce a point forecast and an uncertainty estimate (e.g.,
  forecast error std. dev. or prediction interval) per
  (product, location, period) for the configured horizon.
- FR-2.2 Support at least one classical baseline (e.g.,
  moving average / exponential smoothing) and one learned model (e.g.,
  gradient-boosted trees on lag/calendar features via Spark MLlib),
  selected via config.
- FR-2.3 Report forecast accuracy (e.g., MAPE, WMAPE, RMSE) on a held-out
  window as part of the pipeline output.
- FR-2.4 Forecasting must run distributed across (product, location)
  series using Spark (grouped/partitioned execution), not as a single
  driver-side loop.

### FR-3 Inventory optimization
- FR-3.1 Compute safety stock per (product, location) from forecast
  uncertainty, lead time, and a configurable target service level (cycle
  service level or fill rate).
- FR-3.2 Compute reorder point and order-up-to level (or EOQ-based order
  quantity, configurable) per (product, location).
- FR-3.3 Support multi-echelon propagation: a downstream location's
  demand variability contributes to the upstream (supplying) location's
  inventory policy.
- FR-3.4 Output must include the cost implication (holding cost) of the
  computed policy.

### FR-4 Network/distribution optimization
- FR-4.1 Given per-location net demand (from forecasting) and the lane
  network (cost, capacity, transit time), compute a shipment plan
  (source, destination, product, period, quantity) that satisfies demand
  at minimum transportation + handling cost.
- FR-4.2 Respect lane capacity and location throughput capacity
  constraints.
- FR-4.3 Must produce a feasible solution or a clear infeasibility report
  (which constraints are binding/violated) — never fail silently.
- FR-4.4 Formulated as a linear program (or MIP if discrete
  shipment/lane-selection decisions are enabled); solvable independently
  per product (or per product family) so it can be distributed across
  Spark executors.

### FR-5 Production/procurement planning
- FR-5.1 Given the network plan's required output per plant/period,
  compute make quantities (internal production) and buy quantities
  (supplier procurement) per plant/supplier/period.
- FR-5.2 Respect production capacity, supplier capacity, and minimum
  order quantities (if configured).
- FR-5.3 Minimize total production + procurement cost.
- FR-5.4 Must be consistent with (i.e., feed from/into) the network
  optimization stage — the two may be solved jointly or iteratively; the
  design must state which and why (see `DESIGN.md`).

### FR-6 Orchestration
- FR-6.1 A single entry point runs all stages in order for a given
  scenario and config, writing intermediate and final outputs to a
  configurable location (local disk for dev, object storage for scale).
- FR-6.2 Each stage must also be runnable independently given the
  previous stage's output, for debugging and iteration.
- FR-6.3 Pipeline run metadata (config used, run timestamp, git/version
  info, accuracy/cost summary) must be captured alongside outputs.

### FR-7 Configuration
- FR-7.1 All scenario, model, and optimization parameters are set via a
  single structured config file (YAML), not hardcoded.
- FR-7.2 Config is validated at startup with clear errors on missing/bad
  values.

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Scalability | Runs correctly on a laptop-scale synthetic scenario (≈100s of products × 10s of locations) via local Spark, and is architected (partition-by-key execution, no driver-side collect of large data) so the same code scales to a cluster with larger data without redesign. |
| Reproducibility | Same config + seed ⇒ identical outputs. |
| Determinism of optimization | Solver outputs must be stable (same input ⇒ same solution) or, if not guaranteed by the solver, the design must say so explicitly. |
| Testability | Every module has unit tests; the full pipeline has an integration test on a small fixed scenario, runnable in CI without a cluster or external services. |
| Observability | Structured logging per stage; row counts and key metrics (accuracy, total cost, infeasibility flags) logged at each stage boundary. |
| Extensibility | Forecasting model, solver backend, and cost functions are swappable via config/interfaces, not hardcoded to one library. |
| Portability | No dependency on a specific cloud provider; storage paths are abstracted (local path or object-store URI). |
| Packaging | Standard Python packaging (`pyproject.toml`), pinned dependencies, runnable via `spark-submit` or `python -m`. |
| Documentation | README with quickstart; this requirements doc and the design doc kept up to date as the source of truth for scope. |

## 6. Data Requirements (synthetic, Phase 1)

Minimum tables the generator must produce — full schemas are defined in
`DESIGN.md` §4:

- `products` — product master (id, family, unit cost, unit volume).
- `locations` — plants, distribution centers, demand points (id, type,
  region, capacity).
- `lanes` — allowed shipment paths between locations (source, dest,
  product family, cost/unit, capacity/period, transit time).
- `production_capacity` — plant × product × period capacity and unit
  production cost.
- `supplier_capacity` — supplier × product × period capacity, unit cost,
  minimum order quantity.
- `demand_history` — product × location × period historical demand
  (with configurable trend/seasonality/noise).

## 7. Acceptance Criteria

- A committer can run one command to generate a synthetic scenario, run
  the full pipeline, and get: a forecast accuracy report, an inventory
  policy table, a feasible shipment plan, and a production/procurement
  plan — all internally consistent (e.g., total planned shipments to a
  location roughly track its forecast demand ± policy).
- Turning off a downstream stage (e.g., running only forecasting +
  inventory) works without errors.
- Changing the service-level target or a capacity value in config visibly
  changes the relevant outputs (safety stock, feasibility) on re-run.
- Unit tests pass locally (`pytest`) without a running Spark cluster
  (local mode is sufficient).
- Infeasible scenarios (e.g., demand exceeding total network capacity)
  produce a clear, actionable report rather than a crash or a silently
  wrong answer.

## 8. Open Questions / Risks (to revisit before implementation)

- **Joint vs. sequential solve of network + production/procurement
  (FR-5.4):** sequential is simpler and more distributable; joint is more
  optimal but harder to scale with Spark. Design doc proposes an
  approach — confirm before coding.
- **Solver choice for LP/MIP stages:** open-source solver (CBC via
  PuLP/OR-Tools) is assumed available in the runtime environment;
  confirm no license/infra constraint rules this out.
- **Multi-period vs. single-period per pipeline run:** initial scope
  assumes a rolling set of discrete planning periods (e.g., weeks)
  solved together within one horizon, not a single snapshot.

## 9. Glossary

- **SKU** — Stock-Keeping Unit (a specific product).
- **DC** — Distribution Center.
- **Safety stock** — buffer inventory held to absorb demand/lead-time
  variability at a target service level.
- **Reorder point (ROP)** — inventory level that triggers a new order.
- **Order-up-to level** — target inventory level an order brings stock up to.
- **Lane** — an allowed shipment path between two locations.
- **MIP/LP** — Mixed-Integer / Linear Program.
- **WMAPE** — Weighted Mean Absolute Percentage Error.
