# System Patterns

## Architecture Pattern
To be determined in CREATIVE phase

## Code Organization
To be determined in PLAN/CREATIVE phase

### Proposed Module Structure:
```
sandbox_gcp_bigquery/
├── src/
│   ├── __init__.py
│   ├── logging_util.py    # Structured logging (based on existing pattern)
│   ├── config.py          # Configuration management
│   ├── bigquery_client.py # BigQuery connection
│   ├── query_builder.py   # SQL query construction (MUST enforce timestamp predicates)
│   ├── backoff.py         # Retry logic
│   └── output_handler.py  # File output formatting
├── main.py                # Entry point
├── output/                # Default output directory (git-ignored)
├── .env                   # Configuration (not in git)
├── .env.example           # Template
└── requirements.txt       # Dependencies
```

## Design Patterns to Consider
- **Factory Pattern**: For query builder variations
- **Strategy Pattern**: For different time interval queries
- **Decorator Pattern**: For backoff/retry logic
- **Builder Pattern**: For query construction

## Error Handling Pattern
- Exception hierarchy for different error types
- Centralized error logging
- User-friendly error messages

## Configuration Pattern
- Environment-based configuration (.env file)
- Validation on startup
- Fail-fast for missing required config
- Service name and environment for logging

## Logging Pattern
- Structured JSON logging (similar to existing project)
- No Loki integration initially (deferred to future)
- Console output for local execution
- Labels for service/environment identification

## Testing Strategy
To be determined in PLAN phase

## Logging Strategy
To be determined in PLAN phase

