# 2026-04-09 Feishu Canary And Watch Automation Execution TODO Master v1

## Scope

- freeze Feishu ingress hard-gate contract
- add daily watch automation
- add reproducible fresh-identity Feishu canary runner
- freeze entity recall / canary-driven KB next-step docs

## Execution ledger

### Contract + docs

- [x] Feishu ingress canary contract
- [x] entity-grade recall hardening plan
- [x] canary-driven KB governance plan

### Automation

- [x] add `ops/run_openmind_daily_watch.py`
- [x] add daily watch systemd service
- [x] add daily watch systemd timer
- [x] install/enable timer on host

### Canary replay

- [x] add three real seeded canary cases
- [x] add fresh-identity Feishu canary runner
- [x] run the three cases on live API
- [x] archive results
- [x] record nonterminal cases as fail-closed output rather than green

### Validation

- [x] focused tests for new scripts
- [x] py_compile for new scripts
- [ ] commit and closeout

## Live execution notes

- daily watch live bundle: `artifacts/monitor/openmind_daily_watch/20260409T141022Z/`
- timer enabled: `chatgptrest-openmind-daily-watch.timer`
- Feishu canary live bundle: `artifacts/monitor/feishu_ingress_canary/20260409T141405Z/`
- current seeded case posture:
  - `green_visit_prep`: still `running`
  - `tiger_module_coop`: `completed`
  - `wheel_competition`: still `running`
