# Runtime Parameter Summary

Runtime values take precedence over static YAML when diagnosing navigation precision.
- data_source: `mock_navigation_test`
- THIS_IS_MOCK_DATA

| Node | Parameter name | Runtime value | Possible impact |
|---|---|---:|---|
| `/amcl` | `global_frame_id` | `map` | Frame mismatch here can create systematic pose comparison errors. |
| `/amcl` | `odom_frame_id` | `odom` | Frame mismatch here can create systematic pose comparison errors. |
