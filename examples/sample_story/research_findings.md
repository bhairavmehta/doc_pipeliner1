# Research Findings – Order Tracking Service (US 123456)

Fictional sample input for testing the pipeline. Replace it with your own research findings.

## 1. Carrier feeds
- Carriers A, B and C together handle about 85% of orders. [carrier_volumes.txt]
- Carriers A and B offer webhooks; Carrier C offers polling only (webhooks announced, date not confirmed). [carrier_volumes.txt]

## 2. Status lists
- Each carrier uses its own status codes; most can be mapped to about 8 shared statuses. [status_mapping_notes.txt]
- About 3% of carrier events use rare codes that need manual mapping. [status_mapping_notes.txt]

## 3. Reprocessing
- Keeping raw events allows the history to be rebuilt when the mapping changes.

## Caveats
- Volumes are from one quarter and may change.

## Key sources
- carrier_volumes.txt (sample source)
- status_mapping_notes.txt (sample source)
