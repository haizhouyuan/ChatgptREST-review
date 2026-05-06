# 2026-04-03 Maxwell Redteam Planning Task Checkpoint Preflight Snapshot Walkthrough v1

## Review request

I asked Maxwell to redteam a narrow batch:
- seed material preflight snapshot into planning checkpoint
- persist it through `MeetingTaskStore`
- expose it on first planning-task response
- verify writeback semantics

## First review result

Maxwell rejected the first version.

The main blocker was real:
- empty material lists were ignored during checkpoint patch normalization
- so a later patch could say `ready/pending=0` but still leave stale blocker lists behind

## Fix made after review

I changed the checkpoint patch semantics narrowly:
- the three `source_material_preflight_*` list fields now preserve explicit empty-list writes
- those three fields overwrite old values when present in the patch
- unrelated checkpoint list behavior was left alone

## Second review result

Maxwell approved after the fix.

Its remaining advice was to keep the completion wording narrow:
- this is snapshot persistence plus explicit update/clear support
- not an auto-evolving material state model
