# Contract status

Generated from PactFlow on 2026-11-25 14:55 UTC by the deploy of [`8f2f481`](https://github.com/uzhauniak/pr-quality-gate/commit/8f2f48123a71c12da0994e41a4d159f4a2b01dc8) ([CI run](https://github.com/uzhauniak/pr-quality-gate/actions/runs/45637967385)).

## Contracts

| Consumer → provider | Interactions | Pact |
|---|---|---|
| quotes → pricing | a price request for a known tariff; a price request for an unknown tariff | [pacts/quotes-pricing.json](pacts/quotes-pricing.json) |
| billing → quotes | a request for a quote that does not exist; a request for an accepted quote | [pacts/billing-quotes.json](pacts/billing-quotes.json) |

## can-i-deploy → production

### pricing

**YES**: `pricing` at `8f2f481` against what is recorded as deployed in `production`.

```text
┌──────────┬──────────────────────────────────────────┬──────────┬──────────────────────────────────────────┬──────────┬────────┬───────────────────┐
│ CONSUMER ┆ C.VERSION                                ┆ PROVIDER ┆ P.VERSION                                ┆ SUCCESS? ┆ RESULT ┆ VERIFICATION TYPE │
╞══════════╪══════════════════════════════════════════╪══════════╪══════════════════════════════════════════╪══════════╪════════╪═══════════════════╡
│ quotes   ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ pricing  ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ true     ┆ 1      ┆ CDCT              │
└──────────┴──────────────────────────────────────────┴──────────┴──────────────────────────────────────────┴──────────┴────────┴───────────────────┘

VERIFICATION RESULTS
--------------------
1. https://vza.pactflow.io/pacts/provider/pricing/consumer/quotes/pact-version/b29432c3362b8fd9148453e2a46d01d98b604ae4/metadata/Y3ZuPThmMmY0ODEyM2E3MWMxMmRhMDk5NGU0MWE0ZDE1OWY0YTJiMDFkYzg/verification-results/232 (success)


All required verification results are published and successful


✅ Computer says yes \o/
```

### quotes

**YES**: `quotes` at `8f2f481` against what is recorded as deployed in `production`.

```text
┌──────────┬──────────────────────────────────────────┬──────────┬──────────────────────────────────────────┬──────────┬────────┬───────────────────┐
│ CONSUMER ┆ C.VERSION                                ┆ PROVIDER ┆ P.VERSION                                ┆ SUCCESS? ┆ RESULT ┆ VERIFICATION TYPE │
╞══════════╪══════════════════════════════════════════╪══════════╪══════════════════════════════════════════╪══════════╪════════╪═══════════════════╡
│ billing  ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ quotes   ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ true     ┆ 1      ┆ CDCT              │
├╌╌╌╌╌╌╌╌╌╌┼╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┼╌╌╌╌╌╌╌╌╌╌┼╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┼╌╌╌╌╌╌╌╌╌╌┼╌╌╌╌╌╌╌╌┼╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┤
│ quotes   ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ pricing  ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ true     ┆ 1      ┆ CDCT              │
└──────────┴──────────────────────────────────────────┴──────────┴──────────────────────────────────────────┴──────────┴────────┴───────────────────┘

VERIFICATION RESULTS
--------------------
1. https://vza.pactflow.io/pacts/provider/quotes/consumer/billing/pact-version/45c8d4e12ef44d1bfd3b3a7fa1cc5a43ca6aa2d4/metadata/Y3ZuPThmMmY0ODEyM2E3MWMxMmRhMDk5NGU0MWE0ZDE1OWY0YTJiMDFkYzg/verification-results/233 (success)
2. https://vza.pactflow.io/pacts/provider/pricing/consumer/quotes/pact-version/b29432c3362b8fd9148453e2a46d01d98b604ae4/metadata/Y3ZuPThmMmY0ODEyM2E3MWMxMmRhMDk5NGU0MWE0ZDE1OWY0YTJiMDFkYzg/verification-results/232 (success)


All required verification results are published and successful


✅ Computer says yes \o/
```

### billing

**YES**: `billing` at `8f2f481` against what is recorded as deployed in `production`.

```text
┌──────────┬──────────────────────────────────────────┬──────────┬──────────────────────────────────────────┬──────────┬────────┬───────────────────┐
│ CONSUMER ┆ C.VERSION                                ┆ PROVIDER ┆ P.VERSION                                ┆ SUCCESS? ┆ RESULT ┆ VERIFICATION TYPE │
╞══════════╪══════════════════════════════════════════╪══════════╪══════════════════════════════════════════╪══════════╪════════╪═══════════════════╡
│ billing  ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ quotes   ┆ 8f2f48123a71c12da0994e41a4d159f4a2b01dc8 ┆ true     ┆ 1      ┆ CDCT              │
└──────────┴──────────────────────────────────────────┴──────────┴──────────────────────────────────────────┴──────────┴────────┴───────────────────┘

VERIFICATION RESULTS
--------------------
1. https://vza.pactflow.io/pacts/provider/quotes/consumer/billing/pact-version/45c8d4e12ef44d1bfd3b3a7fa1cc5a43ca6aa2d4/metadata/Y3ZuPThmMmY0ODEyM2E3MWMxMmRhMDk5NGU0MWE0ZDE1OWY0YTJiMDFkYzg/verification-results/233 (success)


All required verification results are published and successful


✅ Computer says yes \o/
```
