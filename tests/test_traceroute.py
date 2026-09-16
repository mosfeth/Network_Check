from supadiag.traceroute import _parse_tracert_output, run_traceroute

sample_tracert_output = """Tracing route to 8.8.8.8 over a maximum of 30 hops:

  1     1 ms     1 ms     1 ms  192.168.1.1
  2     8 ms     7 ms     8 ms  192.168.1.254
  3    12 ms    11 ms    12 ms  10.0.0.1
  4    15 ms    14 ms    15 ms  10.0.0.13
  5    18 ms    17 ms    18 ms  10.0.0.6
  6    22 ms    21 ms    22 ms  10.0.0.14
  7    25 ms    24 ms    25 ms  10.0.0.18
  8    30 ms    29 ms    30 ms  8.8.8.8

Trace complete."""

sample_tracert_with_timeout = """Tracing route to 8.8.8.8 over a maximum of 30 hops:

  1     1 ms     1 ms     1 ms  192.168.1.1
  2     *        *        *     Request timed out.
  3    12 ms    11 ms    12 ms  10.0.0.1
  4     *        *        *     Request timed out.
  5    18 ms    17 ms    18 ms  10.0.0.6
  6    22 ms    21 ms    22 ms  10.0.0.14
  7    25 ms    24 ms    25 ms  10.0.0.18
  8    30 ms    29 ms    30 ms  8.8.8.8

Trace complete."""

sample_tracert_less_than_ms = """Tracing route to 8.8.8.8 over a maximum of 30 hops:

  1     <1 ms    <1 ms    <1 ms  192.168.1.1
  2     <1 ms    <1 ms    <1 ms  192.168.1.254
  3     1 ms     1 ms     1 ms  10.0.0.1
  4     5 ms     5 ms     5 ms  8.8.8.8

Trace complete."""


def test_parse_basic_tracert():
    hops = _parse_tracert_output(sample_tracert_output)
    assert len(hops) == 8, f"Expected 8 hops, got {len(hops)}"
    assert hops[0].hop == 1
    assert hops[0].ip == "192.168.1.1"
    assert hops[7].hop == 8
    assert hops[7].ip == "8.8.8.8"
    print("PASS: test_parse_basic_tracert")


def test_parse_with_timeout():
    hops = _parse_tracert_output(sample_tracert_with_timeout)
    # Timeouts (sem latência) são incluídos como hops com loss=100%
    assert len(hops) == 8, f"Expected 8 hops, got {len(hops)}"
    assert hops[0].hop == 1
    assert hops[1].hop == 2  # Timeout hop
    assert hops[1].loss == 100.0
    assert hops[1].latencies == []
    assert hops[2].hop == 3
    assert hops[6].hop == 7
    assert hops[7].hop == 8
    print("PASS: test_parse_with_timeout")


def test_parse_less_than_ms():
    hops = _parse_tracert_output(sample_tracert_less_than_ms)
    assert len(hops) == 4, f"Expected 4 hops, got {len(hops)}"
    assert hops[0].hop == 1
    assert hops[3].hop == 4
    print("PASS: test_parse_less_than_ms")


def test_run_traceroute():
    result = run_traceroute("8.8.8.8", max_hops=30)
    print(f"Total hops: {result.total_hops}")
    print(f"Destination reached: {result.destination_reached}")
    print(f"Target IP: {result.target_ip}")
    print("PASS: test_run_traceroute (executed)")


if __name__ == "__main__":
    test_parse_basic_tracert()
    test_parse_with_timeout()
    test_parse_less_than_ms()
    test_run_traceroute()
