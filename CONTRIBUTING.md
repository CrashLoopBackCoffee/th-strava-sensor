# Contributing Guidelines

Thank you for your interest in contributing to Strava Sensor! This document provides guidelines and instructions for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.13+
- Git
- uv package manager

### Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/th-strava-sensor.git
   cd th-strava-sensor
   ```

2. **Install development dependencies**
   ```bash
   pip install uv
   uv sync
   ```

3. **Install pre-commit hooks**
   ```bash
   uv run pre-commit install
   ```

4. **Run tests to verify setup**
   ```bash
   uv run pytest tests/ -v
   ```

### Development Environment

The project uses several tools to maintain code quality:

- **uv**: Package management and virtual environment
- **ruff**: Code linting and formatting
- **pyright**: Static type checking
- **pytest**: Testing framework
- **pre-commit**: Git hooks for quality checks

## Code Standards

### Python Style

We follow PEP 8 with some project-specific configurations:

- **Line length**: 100 characters
- **Quote style**: Single quotes preferred
- **Import organization**: Groups separated, sorted alphabetically
- **Type hints**: Required for all public APIs

### Code Quality Tools

All code must pass these checks before merging:

```bash
# Linting and formatting
uv run ruff check --fix
uv run ruff format

# Type checking
uv run pyright

# Testing
uv run pytest tests/ --cov --cov-report=term-missing
```

### Pre-commit Hooks

Pre-commit hooks automatically run quality checks:

- **check-toml**: Validate TOML syntax
- **detect-aws-credentials**: Security check
- **detect-private-key**: Security check
- **end-of-file-fixer**: Ensure files end with newline
- **trailing-whitespace**: Remove trailing spaces
- **pretty-format-json**: Format JSON files
- **ruff**: Linting and formatting
- **pyright**: Type checking
- **yamllint**: YAML validation

## Architecture Guidelines

### Modular Design

- **Single Responsibility**: Each class/module has one clear purpose
- **Interface Segregation**: Small, focused interfaces
- **Dependency Injection**: Pass dependencies explicitly
- **Abstract Base Classes**: Use ABC for extensible components

### Error Handling

- **Typed Exceptions**: Use specific exception types
- **Graceful Degradation**: Continue processing when possible
- **Logging**: Use appropriate log levels
- **User-Friendly Messages**: Clear error messages for end users

### Type Safety

- **Type Hints**: All public APIs must have type hints
- **Pydantic Models**: Use for data validation
- **Generic Types**: Use TypeVar for reusable generic code
- **Union Types**: Use `|` syntax (Python 3.10+)

## Testing Guidelines

### Test Structure

```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── fixtures/            # Test data files
│   └── activity.fit
├── test_fitfile.py      # FIT file processing tests
├── test_sources.py      # Source integration tests
└── test_mqtt.py         # MQTT publishing tests
```

### Writing Tests

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test component interactions
3. **Fixtures**: Use pytest fixtures for reusable test data
4. **Mocking**: Mock external dependencies (APIs, files)
5. **Coverage**: Aim for >90% test coverage

### Test Naming

```python
def test__component__scenario():
    """Test that component handles scenario correctly."""
    pass

def test__fitfile__parse_corrupted():
    """Test that FIT file parser handles corrupted files."""
    pass
```

### Test Categories

- **Happy Path**: Normal operation scenarios
- **Error Cases**: Exception handling
- **Edge Cases**: Boundary conditions
- **Integration**: Component interaction

## Contributing Process

### 1. Issue First

- Check existing issues before creating new ones
- Use issue templates when available
- Provide clear reproduction steps for bugs
- Include relevant system information

### 2. Branch Strategy

```bash
# Create feature branch
git checkout -b feature/description
git checkout -b fix/issue-number
git checkout -b docs/update-readme
```

### 3. Development Workflow

1. **Write tests first** (TDD approach recommended)
2. **Implement minimal changes** to make tests pass
3. **Refactor** for clarity and performance
4. **Update documentation** if needed
5. **Run all quality checks**

### 4. Commit Messages

Follow conventional commits format:

```
type(scope): description

feat(sources): add Wahoo device support
fix(mqtt): handle connection timeouts
docs(readme): update installation instructions
test(fitfile): add corrupted file test cases
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `style`, `chore`

### 5. Pull Request Process

1. **Update from main** before creating PR
2. **Write clear PR description** explaining changes
3. **Reference related issues** using keywords
4. **Include testing evidence** (test results, screenshots)
5. **Request review** from maintainers

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] Tests pass locally
- [ ] Added new tests for changes
- [ ] Manual testing completed

## Related Issues
Fixes #123
```

## Code Review Guidelines

### For Contributors

- **Self-review first**: Check your own code before requesting review
- **Small PRs**: Keep changes focused and reviewable
- **Responsive**: Address feedback promptly
- **Learn**: Use feedback as learning opportunities

### For Reviewers

- **Be constructive**: Provide helpful, actionable feedback
- **Focus on logic**: Review functionality and design
- **Check tests**: Ensure adequate test coverage
- **Verify documentation**: Confirm docs match implementation

## Release Process

### Versioning

We use Semantic Versioning (SemVer):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release tag
4. Build and test package
5. Create GitHub release

## Documentation Standards

### Code Documentation

- **Docstrings**: Use Google-style docstrings
- **Type hints**: Document parameter and return types
- **Examples**: Include usage examples when helpful
- **Edge cases**: Document known limitations

### User Documentation

- **Clear structure**: Logical organization
- **Step-by-step**: Detailed instructions
- **Examples**: Working code examples
- **Troubleshooting**: Common issues and solutions

## Security Guidelines

### Sensitive Data

- **Environment variables**: Use for credentials
- **No hardcoded secrets**: Never commit credentials
- **Token rotation**: Support credential updates
- **Minimal permissions**: Request only needed access

### Input Validation

- **URI parsing**: Validate all input URIs
- **File paths**: Prevent path traversal attacks
- **API responses**: Validate external data
- **User input**: Sanitize all user-provided data

## Performance Guidelines

### Optimization Principles

- **Profile first**: Measure before optimizing
- **Simple solutions**: Avoid premature optimization
- **Memory usage**: Monitor memory consumption
- **I/O efficiency**: Minimize network/disk operations

### Common Patterns

- **Lazy loading**: Load data when needed
- **Caching**: Cache expensive operations
- **Batch processing**: Process multiple items together
- **Error handling**: Fail fast on invalid inputs

## Getting Help

### Community Support

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: General questions and ideas
- **Documentation**: Check existing docs first

### Maintainer Contact

- Create GitHub issue for bugs/features
- Use discussions for questions
- Tag maintainers for urgent issues

## Recognition

Contributors are recognized in:
- GitHub contributors list
- Release notes
- Documentation acknowledgments

Thank you for contributing to Strava Sensor!