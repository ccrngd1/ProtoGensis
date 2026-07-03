# Contributing to EntityBind

Thank you for your interest in contributing to EntityBind! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/cabal-ai/entity-bind.git
   cd entity-bind
   ```

2. **Set up development environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Run tests** to ensure everything works:
   ```bash
   pytest
   ```

## Development Workflow

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and ensure:
   - Code follows existing style and conventions
   - New code includes appropriate tests
   - All tests pass: `pytest`
   - Type hints are used where appropriate

3. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```

4. **Push and create a pull request**:
   ```bash
   git push origin feature/your-feature-name
   ```

## Priority Areas

We welcome contributions in these areas:

### 1. Framework Adapters
- **Anthropic adapter** (`tool_use` blocks)
- **LangChain adapter** (tool wrapper / graph node)
- **MCP adapter** (fastmcp proxy)

### 2. Retrieval & Scoring
- **Embedding-based semantic retrieval** (sentence-transformers)
- **Learned/calibrated scorer** (Splink, probabilistic record linkage)
- **Additional phonetic algorithms** (Double Metaphone, NYSIIS)

### 3. Benchmark & Evaluation
- **Extended benchmark tasks** (harder distractors, multi-entity slots)
- **Additional ambiguity conditions**
- **Real-world task datasets**

### 4. Provenance & Observability
- **LangSmith/Braintrust export**
- **Visualization tools** for provenance logs
- **Metrics dashboards**

### 5. Documentation
- **Tutorials** for specific use cases
- **Integration guides** for popular frameworks
- **Performance optimization guides**

## Code Style

- Follow PEP 8 style guidelines
- Use type hints (Python 3.11+ syntax)
- Use Pydantic models for data validation
- Add docstrings for public APIs
- Keep functions focused and modular

## Testing

- Write unit tests for new functionality
- Add integration tests for adapters
- Ensure test coverage remains above 60%
- Test files go in `tests/` directory

## Pull Request Guidelines

1. **Title**: Use clear, descriptive titles
2. **Description**: Explain what changed and why
3. **Tests**: Include tests for new features
4. **Documentation**: Update relevant docs
5. **Breaking changes**: Clearly mark breaking changes

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Tag maintainers for urgent issues

## Code of Conduct

Be respectful, constructive, and professional in all interactions. We're building something useful together.

---

Thank you for contributing to EntityBind!
