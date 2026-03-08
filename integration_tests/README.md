# Integration Tests

Comprehensive integration tests using 16 real-world sample projects to validate the documentation generator across different technology stacks and project types.

## Test Coverage

### Python Projects (4)
- **python-cli-typer**: CLI tool with Typer framework
- **python-library**: Reusable Python package
- **grpc-python**: gRPC service
- **sample-python-app**: FastAPI web application

### Node.js/TypeScript Projects (6)
- **node-cli-commander**: CLI tool with Commander.js
- **sample-nodejs-ts-app**: Express API (TypeScript)
- **sample-nodejs-js-app**: Express API (JavaScript)
- **frontend-vite-react-ts**: React frontend with Vite
- **electron-desktop-ts**: Electron desktop app
- **graphql-apollo-ts**: GraphQL API with Apollo
- **vscode-extension-ts**: VSCode extension
- **github-action-js**: GitHub Action

### Java Projects (3)
- **sample-springboot-app**: Spring Boot REST API
- **spring-batch-job**: Spring Batch processing
- **spring-stream-kafka**: Spring Cloud Stream with Kafka

### Infrastructure (1)
- **terraform-module-demo**: Terraform IaC module

## Running Tests

### Run all integration tests
```bash
pytest integration_tests/ -v
```

### Run specific test file
```bash
pytest integration_tests/test_python_projects.py -v
pytest integration_tests/test_nodejs_projects.py -v
pytest integration_tests/test_java_projects.py -v
pytest integration_tests/test_specialized.py -v
```

### Run with coverage
```bash
pytest integration_tests/ -v --cov=src --cov-report=html
```

### Run specific test
```bash
pytest integration_tests/test_python_projects.py::TestPythonProjects::test_python_cli_typer -v
```

## Test Structure

Each test validates:
1. **Project Type Detection**: Correct identification (CLI, Library, Web API, etc.)
2. **Language Detection**: Primary language and file counts
3. **Interface Extraction**: CLI commands, API endpoints, etc.
4. **Dependency Extraction**: Runtime and dev dependencies
5. **Entry Point Detection**: Main files and entry points

## Fixtures

Shared fixtures are defined in `conftest.py`:
- `samples_dir`: Path to sample projects
- `analyze_project`: Function to analyze a project (LADOM)
- `get_facts`: Function to extract and normalize facts
- `project_analyzer`, `fact_extractor`, `fact_normalizer`: Component instances

## Assertion Helpers

Custom assertion helpers for better error messages:
- `assert_project_type(facts, ProjectType.CLI)`
- `assert_primary_language(facts, "Python")`
- `assert_has_interface(facts, "CLI")`
- `assert_has_dependencies(facts, "runtime", min_count=2)`
- `assert_has_entry_points(facts, min_count=1)`

## Expected Results

Target: **80%+ pass rate** across all integration tests

Each test may fail initially due to:
- Missing analyzer features
- Incomplete project type detection logic
- Framework detection limitations

Failures help identify areas for improvement in the fact extraction pipeline.
