# Pull Request# Pull Request



## Summary## Summary



Short description of the change and the intent.Short description of the change and the intent.



## Changes## Changes



- What changed (files, docs, behaviour)- What changed (files, docs, behaviour)

- Is this a docs-only change? (yes / no)- Is this a docs-only change? (yes / no)



## How to test (quick)## How to test (quick)



- Run smoke locally:- Run smoke locally:



```powershell```powershell

python -m cli.runner flow --run-id smoke-localpython -m cli.runner flow --run-id smoke-local

``````



- Check artifacts under `artifacts/smoke-local/`- Check artifacts under `artifacts/smoke-local/`



## Reviewer checklist## Reviewer checklist



- [ ] Docs updated (README/DEVELOPER_GUIDE) when public behaviour changes- [ ] Docs updated (README/DEVELOPER_GUIDE) when public behaviour changes

- [ ] `docs/PHASE_INDEX.json` included or auto-generated- [ ] PHASE_INDEX.json included or auto-generated

- [ ] CI smoke artifacts available or CI notes provided- [ ] CI smoke artifacts available or CI notes provided

- [ ] No new lint errors- [ ] No new lint errors



## Description## Notes



- What changed and whyAdd any CI artifact links, environment notes, or special instructions for reviewers.



## How to test / verify## Description



- Steps to reproduce locally (commands)- What changed and why



## Checklist## How to test / verify



- [ ] Code follows style guidelines (lint)- Steps to reproduce locally (commands)

- [ ] Tests added / updated

- [ ] Docs updated if needed## Checklist

- [ ] Artifacts attached or instructions to reproduce

- [ ] Code follows style guidelines (lint)

## Notes for reviewers- [ ] Tests added / updated

- [ ] Docs updated if needed

- Anything special to look out for- [ ] Artifacts attached or instructions to reproduce


## Notes for reviewers

- Anything special to look out for
