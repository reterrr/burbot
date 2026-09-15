# Extraction — Layer 3

Layer 3 stores **evidence** observed on one source-processing workflow. It does not
write canonical `BusinessObjectFieldValue` rows. Canonicalization/reconciliation is
a later business-layer operation.

## Boundary

The browser or Firefox extension selects values from the rendered source and sends
the selected text plus character offsets to the API. `ExtractionService` does not
own a browser session. Its responsibilities are persistence, provenance and domain
validation.

A successful observation is tied to:

- one active `Workflow`, therefore one `source_id` and one `source_snapshot_id`;
- one `BusinessObjectField` belonging to the submitted `BusinessObject`;
- the exact current immutable `SourceObjectFieldTracking.id` (Layer 2 version ID);
- one or more ordered concrete values selected from the source snapshot.

The service locks the source row before resolving tracking versions. Layer 2 uses
the same source lock for SCD2 tracking mutations, so an observation cannot race a
binding rollover or source archival.

## API

`POST /extractions`

```json
{
  "workflow_id": 90,
  "field_observations": [
    {
      "object_id": 40,
      "concrete_values": [
        {
          "snapshot_id": 100,
          "values": [
            {
              "concrete_value": "Generator Kompetencji 3.0",
              "char_start": 12,
              "char_end": 37,
              "token_class_id": "text",
              "object_field_id": 50
            }
          ]
        }
      ]
    }
  ]
}
```

All submitted `snapshot_id` values must equal the workflow's snapshot. Values are
grouped by `object_field_id`, producing one `FieldObservation` per concrete object
field and preserving the submitted value order.

`GET /extractions` lists runs and accepts `workflow_id`, `source_id`, `offset` and
`limit`. `GET /extractions/{run_id}` returns the run with observations and concrete
evidence.

## Layer 2 integration

`FieldObservation` stores both `source_field_tracking_id` and
`source_object_field_tracking_id`. The latter is the bigint ID of the exact SCD2
tracking row, not the public stable UUID. This is the shape required by
`SourcesService.record_tracking_observation(...)` validation.

The migration model loader imports Layer 3 after the business, source and task
models and then calls `register_evidence_references()`. This completes the reverse
Layer 2 foreign keys for `last_observation_id` and `baseline_observation_id`.

## Migration and verification

This change follows the repository's model-first migration policy; it does not add a
handwritten Alembic revision.

```bash
python -m alembic revision --autogenerate -m "add extraction layer"
python -m alembic upgrade head
python -m pytest tests/test_extraction.py -q
```
