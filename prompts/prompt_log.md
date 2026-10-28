# Journey Drop-off Analysis Using Synthetic Data

## Overview

This project explores customer-journey drop-offs and high-friction paths by connecting synthetic events from web, app, customer support, and purchase activity. It demonstrates an analytics workflow for preparing event data, validating data quality, analyzing journey progression, and producing outputs that help identify where customers may encounter friction.

**Repository:** [SovitT/Journey_Dropoff_Synthetic_data](https://github.com/SovitT/Journey_Dropoff_Synthetic_data)

## Problem Statement

Customer interactions often happen across multiple channels. When web, app, support, and purchase events are stored separately, it can be difficult to understand where customers abandon a journey, repeat an action, encounter an issue, or require support before completing a purchase.

This project uses synthetic data to connect those events and identify potential drop-off points and friction patterns without using real customer information.

## Objectives

- Represent customer activity across web, app, support, and purchase touchpoints.
- Organize related events into customer journeys or sessions.
- Measure progression through a journey funnel and identify where activity decreases.
- Surface potential high-friction patterns and exception cases.
- Apply data-quality checks and preserve traceability of generated or analyzed data.
- Produce reproducible outputs that can be reviewed and explained.

## Key Questions

1. At which journey step do the most users drop off?
2. Which paths appear to have higher friction or repeated activity?
3. How do support interactions relate to purchase completion or abandonment?
4. Are there missing, duplicated, or inconsistent events that could affect the analysis?
5. Which assumptions, rules, and exceptions influence the reported results?

## Project Workflow

1. **Prepare data** — use the synthetic starter data and/or the project's data-generation workflow.
2. **Process events** — organize related activity across the available touchpoints.
3. **Validate data** — check for relevant quality issues before interpreting metrics.
4. **Analyze journeys** — calculate funnel progression and inspect possible drop-off or friction patterns.
5. **Review exceptions** — inspect records or paths that do not follow the expected journey.
6. **Generate outputs** — use the project's reports and analysis artifacts to review results.
7. **Document findings** — record assumptions, limitations, and verification steps.

## Repository Structure

```text
Journey_Dropoff_Synthetic_data/
├── data/
│   └── starter/       # Starter input data
├── docs/              # Project documentation and data definitions
├── prompts/           # AI prompt history and related records
├── reports/           # Generated or supporting analysis outputs
├── src/               # Source code for the workflow
├── tests/             # Test and validation code
├── .gitignore
├── requirements.txt   # Python dependencies
└── README.md
```

## Technology

The repository uses Python and the dependencies listed in [`requirements.txt`](requirements.txt). The project is organized into source code, tests, starter data, documentation, and reports.

## Getting Started

### Prerequisites

- Python version compatible with the packages in `requirements.txt` (Python 3.10+ is a reasonable starting point; confirm against the project's dependencies).
- Git
- A terminal such as PowerShell, Command Prompt, or a Unix shell

### 1. Clone the repository

```bash
git clone https://github.com/SovitT/Journey_Dropoff_Synthetic_data.git
cd Journey_Dropoff_Synthetic_data
```

### 2. Create and activate a virtual environment

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt:

```bat
.venv\Scripts\activate.bat
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the workflow

Review the scripts in `src/` and use the project's actual entry point and command-line options. If `src/run_all.py` exists in your checked-out version, the following may be used:

```bash
python src/run_all.py
```

Confirm this command against the files in the repository before relying on it in an evaluation. If the entry point has a different name, replace the example with the exact command that you verified.

### 5. Run tests

Review the tests in `tests/` and run the test framework used by the project. If the project uses `pytest`, run:

```bash
python -m pytest -q
```

Only report tests as passing after actually running them. A successful test command verifies only the checks that it executes.

## Outputs and Interpretation

Depending on the workflow executed, the project's reports and outputs can be used to inspect:

- Journey funnel counts and conversion/drop-off rates.
- Potential high-friction steps or repeated interactions.
- Exceptions and records requiring review.
- Data-quality validation results.

Interpret these findings as patterns in **synthetic data**, not as evidence about real customers. A drop-off or repeated event may indicate friction, but it does not by itself establish the cause.

## Data and Privacy

- Use synthetic or non-sensitive sample data.
- Do not commit credentials, API keys, access tokens, private customer information, or other secrets.
- Avoid committing unnecessary large generated datasets or temporary files.
- Keep starter data and committed reports only when they are useful for reproducing or reviewing the project.

## Documentation

Additional project documentation is maintained in `docs/` and `prompts/`. These files should describe data fields, source and generation assumptions, AI assistance, and prompts actually used during development. Ensure the documentation matches the code and data currently in the repository.

## Assumptions and Limitations

- The data is synthetic and may not reflect real customer behavior or real-world event frequencies.
- Funnel definitions and friction rules depend on the implementation's assumptions.
- A relationship between support activity and drop-off does not prove causation.
- Results depend on input data quality, event linkage, validation rules, and analysis logic.
- Known gaps, unimplemented requirements, and checks that were not independently verified should be stated explicitly.

## Reproducibility Checklist

- [ ] Clone the repository into a clean directory.
- [ ] Install dependencies from `requirements.txt`.
- [ ] Run the documented entry point.
- [ ] Run available tests or validation checks.
- [ ] Confirm expected outputs are produced.
- [ ] Check that README commands match the current source files.
- [ ] Review `docs/` and `prompts/` for consistency with the implementation.
- [ ] Confirm that no secrets or private data are committed.

## AI Assistance

AI tools have been used for planning, troubleshooting, or documentation. The prompt log and AI-use disclosure should accurately identify the tools used and explain how suggestions were reviewed. The submitted work should be understood and verifiable by the project author.

## Author

**Sovit Thakre**  
GitHub: [@SovitT](https://github.com/SovitT)
