# Compare iteration — skill 863dbaa509ac — model us.anthropic.claude-sonnet-4-5-20250929-v1:0

| scenario | with_skill_pass | without_skill_pass | pass_delta |
|---|---|---|---|
| conditional-template | False | False | 0 |
| invalid-typed-value | True | False | 1 |
| nonexistent-template | True | False | 1 |
| plain-request | False | False | 0 |
| prefixed-tool-names | False | False | 0 |
| preflight-catalog-only | True | False | 1 |
| preflight-denied-call | True | False | 1 |
| preflight-empty-catalog | True | False | 1 |
| preflight-no-capabilities | True | False | 1 |
| secrets-template | False | False | 0 |
| synthetic-tenth | True | True | 0 |
| task-failure | False | False | 0 |
| time-pressure | False | False | 0 |
| under-specified-request | False | False | 0 |

mean pass_rate: with=0.50 without=0.07 delta=0.43
