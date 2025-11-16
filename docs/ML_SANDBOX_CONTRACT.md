# Stage 11 ML Sandbox Contract

The ML sandbox lives under `artifacts/{run_id}/stage_11_ml_sandbox/` and provides an internal-only playground for incremental ML layers on top of the production BI stack.

- `ml_base_orders.parquet` is the canonical ML base table. It is derived from `stage_10_bi/marts/fact_business.parquet`, which already powers `/api/bi/orders` and `/api/bi/metrics`. The grain stays one row per shipment/order (`entity_id` in the Stage 10 marts).
- Downstream sandbox steps (currently clustering) only run when explicitly invoked via the CLI and never mutate existing BI artifacts.

## Base Table Contract (`ml_base_orders`)

- **Grain:** one row per shipment/order (mirrors `fact_business` grain).
- **Primary identifiers:** `shipment_id` (`entity_id`), `client_id` (`Account_NO`), `carrier_id` (`FORWARD_COMPANY`).
- **Path:** `artifacts/{run_id}/stage_11_ml_sandbox/ml_base_orders.parquet`

| Column | Type | Required | Description |
| --- | --- | --- | --- |
| `shipment_id` | string | ✅ | Unique shipment/order identifier from Stage 10 (`entity_id`). |
| `client_id` | string | ✅ | Billing/client/account identifier (`Account_NO`). Defaults to `UNKNOWN` if null. |
| `carrier_id` | string | ❌ | Forwarder / 3PL id (`FORWARD_COMPANY`). |
| `origin_city` | string | ❌ | Origin city. |
| `city` | string | ✅ | Destination city. |
| `zone` | string | ❌ | Destination hub/zone (`DESTINATION_HUB`). |
| `area_street` | string | ❌ | Final mile street/area label. |
| `sender_name` | string | ❌ | Sender label used for diagnostics. |
| `receiver_name` | string | ❌ | Receiver label used for diagnostics. |
| `status` | string | ✅ | Final network status. |
| `carrier_status` | string | ❌ | Latest carrier-provided status (`3PLSTATUS`). |
| `carrier_last_status` | string | ❌ | Last raw carrier event description. |
| `payment_method` | string | ❌ | COD vs prepaid mode (`RECEIVER_MODE`). |
| `created_at` | datetime tz-aware | ✅ | Shipment creation timestamp (`ts_created`). |
| `promised_date` | datetime | ❌ | Promise or scheduled date (`SCHEDULE_DATE`). |
| `delivered_at` | datetime | ❌ | Actual delivery timestamp (`ts_delivered`). |
| `delivery_time_hours` | float | ✅ | Lead time (hours) from `lead_time_hours` with fallback to timestamp delta. |
| `sla_days` | float | ✅ | Delivery time converted to days (`delivery_time_hours / 24`). |
| `sla_met` | bool | ❌ | `on_time` flag from Stage 10. |
| `sla_breach` | bool | ❌ | Inverse of `sla_met`; null when SLA status unknown. |
| `is_rto` | bool | ❌ | Return-to-origin indicator (`rto_flag`). |
| `is_cod` | bool | ❌ | Cash-on-delivery indicator. |
| `cod_amount` | float | ❌ | COD amount for the shipment. |
| `weight_kg` | float | ❌ | Captured shipment weight. |
| `pieces` | float | ❌ | Number of pieces. |
| `delivery_attempts` | float | ❌ | `D_ATTEMPT` from Stage 10. |
| `call_attempts` | float | ❌ | `CALL_ATTEMPT`. |
| `row_deeplink` | string | ❌ | BI deeplink (kept for traceability). |
| `kpi_sla_pct`, `kpi_rto_pct`, `kpi_cod_rate` | float | ❌ | Snapshot KPIs propagated from Stage 09 validation. |

**Source:** `stage_10_bi/marts/fact_business.parquet`

**Limitations & caveats**

- Some dimensional fields (e.g. promised dates or carrier statuses) can be null for legacy runs or sources with incomplete telemetry.
- SLA indicators rely on Stage 09 calculations, so rerunning the ML sandbox without a fresh Stage 10 mart will reuse whatever logic was embedded at the time of the BI run.
- The sandbox never mutates Stage 10 artifacts; it is safe to delete `stage_11_ml_sandbox` directories for failed experiments.

## Current Sandbox Outputs (ML-S1)

When `run_client_clustering` executes it produces, under the same stage directory:

- `client_clusters.parquet` — aggregated KPIs per `client_id` with an assigned `cluster_id` (low-volume clients receive `cluster_id = -1`).
- `cluster_model.joblib` — serialized `StandardScaler + KMeans` bundle plus metadata (feature list, minimum shipment threshold).
- `cluster_metadata.json` — run metadata (`run_id`, counts of clustered/unclustered clients, feature names, cluster size stats, and source/output paths).

Low-volume clients (default `< 5` shipments in the run) are tagged as `cluster_id = -1` so downstream consumers can treat them as “unsegmented” while still tracking their KPIs.
