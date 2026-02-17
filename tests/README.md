# Tests

Project tests are organized by app/project. Add a subfolder per project to keep tests grouped and easy to run independently.

## Structure

```
tests/
├── README.md           # this file
├── sports_schedules/   # tests for app/projects/sports_schedules
│   └── test_query_builder.py
├── betfake/            # future: tests for app/projects/betfake
└── ...
```

## Running tests

With venv activated:

```bash
# All tests
python -m unittest discover -s tests -v
pytest tests/ -v

# Single project
python -m unittest tests.sports_schedules.test_query_builder -v
pytest tests/sports_schedules/ -v
```
