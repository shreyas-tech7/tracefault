# Demo

A real terminal session, recorded on 2026-11-21 in this repo after `./init.sh`. The commands ran as `.venv/bin/tracefault`. The prompt shows them short. Nothing here needs a sign-in or the network.

The demo traces come from the generator (seed 7, 2 traces per failure type and 4 clean traces). Their truth is in `examples/demo-truth.json`. One trace holds a planted handoff drop and also polls a status three times as benign noise, so it gets a false `repeated_calls` finding too. That is the kind of false alarm the README results count.

The report written by the demo is the same kind of page as [report-example.html](report-example.html).

```text
$ tracefault demo --out /tmp/tracefault-demo
demo: wrote 20 generated traces to /tmp/tracefault-demo/demo.jsonl
FAIL handoff_drop trace=c94dbca3a0aac36098b2cc2bd8183194 span=8263dfe574de7399: handoff to invoke_agent refund_agent dropped required field order_id
FAIL budget_exhaustion trace=3ce9d97dcbee500fe7ee5fc324bdb2e1 span=42a21c402364f957: used 44479 tokens of a 34900 token budget
FAIL wrong_tool trace=13830d71939b53182e4e349d98729e7c span=966d513b1d00909c: 4 calls to tools outside the task list: lookup_invoice, refund_payment, search_flights
FAIL wrong_tool trace=6fdf5924754ec21ef66b01d4921da2e0 span=828b4136d3b97429: 3 calls to tools outside the task list: get_weather, run_tests, search_flights
FAIL repeated_calls trace=fdd9e4a62bce19a285ed7361c5c8a4b5 span=793b2b023a60e4e8: geocode called 3+ times with the same arguments
FAIL repeated_calls trace=5e3eaa60c736ba80622598514f31c827 span=f72fbf666f69e87a: check_status called 3+ times with the same arguments
FAIL handoff_drop trace=5e3eaa60c736ba80622598514f31c827 span=fdbea13e284142e1: handoff to invoke_agent refund_agent dropped required field order_id
FAIL tool_error_loop trace=766bb31ed04d259b3717bd5c2d6a9a5f span=9972d06263739360: 3+ tool errors in a row on search_kb: ConnectionError: upstream returned 503 for request 7f3a9c21
FAIL timeout trace=ebf7c99c18fa6eb9eb2b67d8b081abd1 span=1ff65255845a94f3: lookup_invoice ran 33.1 s (timeout 30 s): timeout
FAIL context_overflow trace=d634d54a7dc843565f6ef306e13d6975 span=32bd008f56f49d64: context near its limit (16058 of 16384 tokens), then truncated
FAIL timeout trace=edbd57da8cafe1f6151b9267f9ed2125 span=8b3f4534c496af2f: refund_payment ran 30.5 s (timeout 30 s): TimeoutError: tool did not answer in 30 s
FAIL unknown_tool trace=85a6c844be645a80d5282639fa798b13 span=d1195d24734e0717: call to a tool that does not exist: search_flight_v2
FAIL repeated_calls trace=e09ab022e0d3f2380c27c73a0d502577 span=df0b91e1fc0ab620: search_flights called 3+ times with the same arguments
FAIL tool_error_loop trace=b923e7b81726cd9bba602f26bf0661a5 span=e6f4f56a7ed9fc0d: 3+ tool errors in a row on book_flight, search_flights: PermissionError: token for user 4411 lacks scope billing:write
FAIL unknown_tool trace=9e25f4983c028716eca5cf68f5a8250e span=0a99f27608f43a24: call to a tool that does not exist: kb_search
FAIL context_overflow trace=b5cd02d1034539a70366c12fb15220c3 span=0729a3671fd653e7: context near its limit (29699 of 32768 tokens), then truncated
FAIL budget_exhaustion trace=2d4f409454129039aa0929ba7cb76def span=4f73c8dbb4c50a9b: budget exceeded: token limit reached
scanned 20 traces: 16 with findings, 17 findings in 14 clusters
     2  budget_exhaustion | budget exceeded: token limit reached | -
     2  context_overflow | context near its limit (N of N tokens), then truncated | -
     2  handoff_drop | handoff to invoke_agent refund_agent dropped required field order_id | -
     1  repeated_calls | check_status called N+ times with the same arguments | check_status > check_status > check_status
     1  repeated_calls | geocode called N+ times with the same arguments | geocode > geocode > geocode
wrote /tmp/tracefault-demo/report.html
demo: scan exit code 1 (1 means failures were found, as planted)

$ tracefault scan examples/otel_genai.json; echo "exit code $?"
FAIL tool_error_loop trace=4bf92f3577b34da6a3ce929d0e0e4736 span=00f067aa0ba90207: 3+ tool errors in a row on get_weather: ConnectionError: upstream returned 503
scanned 1 traces: 1 with findings, 1 findings in 1 clusters
     1  tool_error_loop | connectionerror: upstream returned N | get_weather > get_weather > get_weather
exit code 1

$ tracefault scan examples/simple.jsonl --fail-on timeout -q; echo "exit code $?"
scanned 1 traces: 1 with findings, 1 findings in 1 clusters
     1  tool_error_loop | connectionerror: upstream returned N | get_weather > get_weather > get_weather
exit code 0

$ tracefault scan missing.jsonl; echo "exit code $?"
tracefault: error: missing.jsonl: cannot read (FileNotFoundError)
exit code 2
```
