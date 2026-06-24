# CodeResearch Agent

Multi-agent research analysis platform for large open-source code repositories.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Start infrastructure (Redis + etcd + MinIO + Milvus)
make docker-up

# Set up environment
cp .env.example .env
# Edit .env with your LLM_API_KEY

# Run development server
make dev
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/tasks` | Submit a research task |
| `GET` | `/tasks/{task_id}` | Get task status |
| `DELETE` | `/tasks/{task_id}` | Cancel a task |
| `GET` | `/tasks/{task_id}/events` | SSE event stream |
| `GET` | `/reports/{task_id}?format=json|markdown|html` | Get report |
| `GET` | `/evidence/{task_id}?source_type=` | Get evidence chain |
| `GET` | `/tools` | List available tools |
| `POST` | `/tools/register` | Register a tool |

## Example

```bash
# Submit a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze the architecture", "repo_urls": ["https://github.com/psf/requests"], "max_depth": 3}'

# Track progress
curl http://localhost:8000/tasks/{task_id}

# Get report
curl http://localhost:8000/reports/{task_id}?format=markdown
```

## Architecture

```
FastAPI → LangGraph StateGraph:
  Planner → Researcher → CodeReader → Executor → Reviewer ↔ Reporter
```

See `docs/SOLUTION.md` for full architecture documentation.

## Development

```bash
make test      # Run tests
make lint      # Lint code
make docker-up # Start infrastructure
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | — | LLM API key (required) |
| `LLM_API_BASE` | `https://api.openai.com/v1` | LLM endpoint |
| `LLM_MODEL` | `gpt-4o` | Model name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis |
| `MILVUS_HOST` | `localhost` | Milvus host |
| `MILVUS_PORT` | `19530` | Milvus port |
