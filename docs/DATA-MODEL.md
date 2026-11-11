# Collaboration data model

Use these fields when proposing editable records for waterbody locations, lift intakes, and outflow points.

## Waterbody

- `waterbody_id`
- `name`
- `aliases`
- `type`: reservoir, tank, pond, lake, barrage impoundment, wetland
- `geometry`
- `source_dataset`
- `source_record_id`
- `source_url`
- `retrieved_at`
- `district`
- `basin`
- `project`
- `confidence`
- `review_status`
- `notes`

## Structure or intake

- `structure_id`
- `name`
- `structure_type`: barrage, weir, regulator, dam, intake, pump house, canal head regulator
- `geometry`
- `connected_waterbody_id`
- `connected_flow_path_id`
- `evidence_type`: official, mapped, field observation, inferred
- `source_url`
- `confidence`
- `notes`

## Outflow or destination

- `destination_id`
- `name`
- `destination_type`: reservoir, canal, command area, balancing reservoir, distribution node, river
- `geometry`
- `project_id`
- `evidence_type`
- `source_url`
- `confidence`
- `notes`

## Inferred connection

- `connection_id`
- `source_intake_id`
- `destination_id`
- `geometry`
- `connection_type`: lift, gravity canal, pipeline, tunnel, inferred transfer
- `directionality`
- `is_surveyed`: true or false
- `evidence_urls`
- `confidence`
- `review_status`
- `notes`

Never use an inferred connection as proof of a surveyed pipeline route.
