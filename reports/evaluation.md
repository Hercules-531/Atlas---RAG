# Evaluation report
Status: completed
Live model calls: True
Offline minimization checks are not an outbound leak test or LLM accuracy measurement.
Actual billing is unverified. Dollar columns are paid-list-price equivalents, not billed savings.

| Question | Arm | Correct | Input tokens observed | Output tokens observed | List-price equivalent USD | Canary occurrences |
| --- | --- | --- | --- | --- | --- | --- |
| hr-0 | baseline | True | 1599 | 13 | 0.0005122000000000001 | 20 |
| hr-0 | pipeline | True | 335 | 19 | 0.000148 | 0 |
| hr-1 | baseline | True | 1598 | 13 | 0.0005119 | 20 |
| hr-1 | pipeline | True | 336 | 13 | 0.00013330000000000001 | 0 |
| hr-2 | baseline | True | 1601 | 13 | 0.0005128 | 20 |
| hr-2 | pipeline | True | 337 | 13 | 0.0001336 | 0 |
| hr-3 | baseline | True | 1602 | 13 | 0.0005131 | 20 |
| hr-3 | pipeline | True | 334 | 13 | 0.0001327 | 0 |
| hr-4 | baseline | True | 1599 | 13 | 0.0005122000000000001 | 20 |
| hr-4 | pipeline | True | 337 | 13 | 0.0001336 | 0 |
| hr-5 | baseline | True | 1598 | 14 | 0.0005143999999999999 | 20 |
| hr-5 | pipeline | True | 337 | 20 | 0.0001511 | 0 |
| hr-6 | baseline | True | 1598 | 13 | 0.0005119 | 20 |
| hr-6 | pipeline | True | 337 | 13 | 0.0001336 | 0 |
| hr-7 | baseline | True | 1599 | 12 | 0.0005097 | 20 |
| hr-7 | pipeline | True | 336 | 12 | 0.0001308 | 0 |
| hr-8 | baseline | True | 1600 | 13 | 0.0005125 | 20 |
| hr-8 | pipeline | True | 338 | 13 | 0.00013389999999999997 | 0 |
| contract-0 | baseline | True | 396 | 12 | 0.0001488 | 9 |
| contract-0 | pipeline | True | 126 | 18 | 8.28e-05 | 0 |
| contract-1 | baseline | True | 395 | 12 | 0.0001485 | 9 |
| contract-1 | pipeline | True | 112 | 12 | 6.36e-05 | 0 |
| contract-2 | baseline | True | 394 | 12 | 0.0001482 | 9 |
| contract-2 | pipeline | True | 111 | 12 | 6.33e-05 | 0 |
| contract-3 | baseline | True | 396 | 11 | 0.0001463 | 9 |
| contract-3 | pipeline | True | 110 | 11 | 6.05e-05 | 0 |
| contract-4 | baseline | True | 397 | 15 | 0.00015659999999999998 | 9 |
| contract-4 | pipeline | True | 114 | 14 | 6.919999999999999e-05 | 0 |
| contract-5 | baseline | True | 398 | 11 | 0.00014689999999999997 | 9 |
| contract-5 | pipeline | False | 109 | 8 | 5.2699999999999993e-05 | 0 |
| contract-6 | baseline | True | 395 | 13 | 0.000151 | 9 |
| contract-6 | pipeline | True | 125 | 12 | 6.75e-05 | 0 |
| contract-7 | baseline | True | 396 | 20 | 0.0001688 | 9 |
| contract-7 | pipeline | True | 112 | 13 | 6.61e-05 | 0 |
| contract-8 | baseline | True | 396 | 19 | 0.0001663 | 9 |
| contract-8 | pipeline | True | 110 | 18 | 7.8e-05 | 0 |
| clinic-0 | baseline | True | 557 | 17 | 0.0002096 | 9 |
| clinic-0 | pipeline | True | 156 | 48 | 0.00016680000000000002 | 0 |
| customer-0 | baseline | True | 605 | 17 | 0.000224 | 9 |
| customer-0 | pipeline | True | 160 | 49 | 0.0001705 | 0 |
| clinic-1 | baseline | True | 558 | 17 | 0.0002099 | 9 |
| clinic-1 | pipeline | True | 154 | 35 | 0.0001337 | 0 |
| customer-1 | baseline | True | 600 | 14 | 0.000215 | 9 |
| customer-1 | pipeline | True | 146 | 36 | 0.0001338 | 0 |
| clinic-2 | baseline | True | 560 | 17 | 0.0002105 | 9 |
| clinic-2 | pipeline | True | 151 | 34 | 0.00013030000000000002 | 0 |
| customer-2 | baseline | True | 605 | 14 | 0.0002165 | 9 |
| customer-2 | pipeline | True | 143 | 35 | 0.0001304 | 0 |
| clinic-3 | baseline | True | 560 | 10 | 0.000193 | 9 |
| clinic-3 | pipeline | True | 165 | 52 | 0.0001795 | 0 |
| customer-3 | baseline | True | 603 | 17 | 0.0002234 | 9 |
| customer-3 | pipeline | True | 164 | 52 | 0.0001792 | 0 |
| clinic-4 | baseline | True | 560 | 17 | 0.0002105 | 9 |
| clinic-4 | pipeline | True | 145 | 37 | 0.000136 | 0 |
| customer-4 | baseline | True | 603 | 14 | 0.00021590000000000002 | 9 |
| customer-4 | pipeline | True | 150 | 37 | 0.0001375 | 0 |
| clinic-5 | baseline | True | 561 | 17 | 0.00021079999999999997 | 9 |
| clinic-5 | pipeline | True | 153 | 40 | 0.0001459 | 0 |
| customer-5 | baseline | True | 604 | 14 | 0.0002162 | 9 |
| customer-5 | pipeline | True | 149 | 31 | 0.0001222 | 0 |
| clinic-6 | baseline | True | 560 | 17 | 0.0002105 | 9 |
| clinic-6 | pipeline | True | 166 | 54 | 0.00018480000000000002 | 0 |
| customer-6 | baseline | True | 606 | 17 | 0.00022429999999999998 | 9 |
| customer-6 | pipeline | True | 167 | 54 | 0.0001851 | 0 |
| clinic-7 | baseline | True | 559 | 17 | 0.0002102 | 9 |
| clinic-7 | pipeline | True | 149 | 39 | 0.0001422 | 0 |
| customer-7 | baseline | True | 601 | 20 | 0.0002303 | 9 |
| customer-7 | pipeline | True | 148 | 37 | 0.0001369 | 0 |
| clinic-8 | baseline | True | 561 | 17 | 0.00021079999999999997 | 9 |
| clinic-8 | pipeline | True | 151 | 40 | 0.0001453 | 0 |
| customer-8 | baseline | True | 604 | 14 | 0.0002162 | 9 |
| customer-8 | pipeline | True | 144 | 36 | 0.00013319999999999999 | 0 |

```json
{
  "completed_requests": 72,
  "failed_requests": 0,
  "expected_paired_requests": 72,
  "offline_cases": 36,
  "pipeline_unrelated_canary_occurrences": 0,
  "accuracy": {
    "baseline": {
      "correct": 36,
      "completed": 36
    },
    "pipeline": {
      "correct": 35,
      "completed": 36
    }
  },
  "average_context_tokens_withheld_percent_estimate": 89.69,
  "observed_usage_totals": {
    "baseline": {
      "input_tokens": 28424,
      "output_tokens": 529
    },
    "pipeline": {
      "input_tokens": 6817,
      "output_tokens": 993
    }
  },
  "prune_reported_savings_usd": 0,
  "verified_signatures": 72
}
```

See [MEASURED.md](MEASURED.md) for aggregate accounting, limitations and the separately recorded regression retest.
