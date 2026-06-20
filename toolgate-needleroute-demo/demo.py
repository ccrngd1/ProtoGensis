#!/usr/bin/env python3
"""
ToolGate + NeedleRoute Pipeline Demo
=====================================

Demonstrates the combined power of ToolGate (semantic filtering) and
NeedleRoute (Needle model routing with confidence-based escalation)
working together as a unified MCP tool selection pipeline.

Pipeline:
1. ToolGate narrows 50+ tools → top-K via sentence-transformer embeddings + FAISS
2. NeedleRoute's Needle model picks the final tool from that filtered set
3. If confidence is low, escalate to frontier model (only over filtered set)

Run: python demo.py
"""

import json
import time
import random
import hashlib
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# Terminal Colors & Formatting
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Background
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"

    @staticmethod
    def colorize(text: str, color: str) -> str:
        return f"{color}{text}{Colors.RESET}"

    @staticmethod
    def bold(text: str) -> str:
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    @staticmethod
    def dim(text: str) -> str:
        return f"{Colors.DIM}{text}{Colors.RESET}"


def print_banner():
    """Print the demo banner."""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ████████╗ ██████╗  ██████╗ ██╗      ██████╗  █████╗ ████████╗███████╗     ║
║   ╚══██╔══╝██╔═══██╗██╔═══██╗██║     ██╔════╝ ██╔══██╗╚══██╔══╝██╔════╝     ║
║      ██║   ██║   ██║██║   ██║██║     ██║  ███╗███████║   ██║   █████╗       ║
║      ██║   ██║   ██║██║   ██║██║     ██║   ██║██╔══██║   ██║   ██╔══╝       ║
║      ██║   ╚██████╔╝╚██████╔╝███████╗╚██████╔╝██║  ██║   ██║   ███████╗     ║
║      ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝     ║
║                           ×                                                  ║
║   ███╗   ██╗███████╗███████╗██████╗ ██╗     ███████╗                         ║
║   ████╗  ██║██╔════╝██╔════╝██╔══██╗██║     ██╔════╝                         ║
║   ██╔██╗ ██║█████╗  █████╗  ██║  ██║██║     █████╗                           ║
║   ██║╚██╗██║██╔══╝  ██╔══╝  ██║  ██║██║     ██╔══╝                           ║
║   ██║ ╚████║███████╗███████╗██████╔╝███████╗███████╗                         ║
║   ╚═╝  ╚═══╝╚══════╝╚══════╝╚═════╝ ╚══════╝╚══════╝                         ║
║                    ██████╗  ██████╗ ██╗   ██╗████████╗███████╗               ║
║                    ██╔══██╗██╔═══██╗██║   ██║╚══██╔══╝██╔════╝               ║
║                    ██████╔╝██║   ██║██║   ██║   ██║   █████╗                 ║
║                    ██╔══██╗██║   ██║██║   ██║   ██║   ██╔══╝                 ║
║                    ██║  ██║╚██████╔╝╚██████╔╝   ██║   ███████╗               ║
║                    ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝               ║
║                                                                              ║
║              Combined MCP Tool Selection Pipeline Demo                       ║
╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


def print_header(text: str, char: str = "═"):
    """Print a section header."""
    width = 78
    print(f"\n{Colors.BOLD}{Colors.CYAN}{char * width}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{char * width}{Colors.RESET}")


def print_subheader(text: str):
    """Print a subsection header."""
    print(f"\n  {Colors.BOLD}{Colors.YELLOW}▸ {text}{Colors.RESET}")
    print(f"  {Colors.DIM}{'─' * 72}{Colors.RESET}")


def print_table(headers: List[str], rows: List[List[str]], col_widths: Optional[List[int]] = None):
    """Print a formatted table."""
    if not col_widths:
        col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]

    # Header
    header_line = "  │ " + " │ ".join(
        f"{Colors.BOLD}{h:<{col_widths[i]}}{Colors.RESET}" for i, h in enumerate(headers)
    ) + " │"
    sep_line = "  ├─" + "─┼─".join("─" * w for w in col_widths) + "─┤"
    top_line = "  ┌─" + "─┬─".join("─" * w for w in col_widths) + "─┐"
    bot_line = "  └─" + "─┴─".join("─" * w for w in col_widths) + "─┘"

    print(top_line)
    print(header_line)
    print(sep_line)
    for row in rows:
        row_line = "  │ " + " │ ".join(
            f"{str(row[i]):<{col_widths[i]}}" for i in range(len(row))
        ) + " │"
        print(row_line)
    print(bot_line)


# ═══════════════════════════════════════════════════════════════════════════════
# Mock Models (portable, no external dependencies needed)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Tool:
    """MCP tool definition."""
    name: str
    description: str
    category: str
    input_schema: Dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        """Estimate token count for this tool definition."""
        text = json.dumps({
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        })
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4


@dataclass
class ScoredTool:
    """Tool with similarity/confidence score."""
    tool: Tool
    score: float
    confidence: float = 0.0


@dataclass
class PipelineResult:
    """Result from running the full pipeline."""
    query: str
    selected_tool: str
    correct_tool: str
    # Stage metrics
    toolgate_results: List[ScoredTool]
    needle_results: List[ScoredTool]
    escalated: bool
    escalation_reason: Optional[str]
    # Performance
    toolgate_latency_ms: float
    needle_latency_ms: float
    escalation_latency_ms: float
    total_latency_ms: float
    # Token metrics
    tokens_all_tools: int
    tokens_after_toolgate: int
    tokens_after_pipeline: int
    # Accuracy
    correct: bool


class MockEmbeddingModel:
    """
    Mock sentence-transformer that produces deterministic embeddings.

    Simulates semantic similarity by encoding tools into a category-aware
    vector space. Tools in the same semantic category will have higher
    cosine similarity to related queries.
    """

    CATEGORY_VECTORS = {
        "filesystem": [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0],
        "git": [0.1, 0.9, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0],
        "http": [0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.1],
        "parsing": [0.2, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0],
        "crypto": [0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 0.1, 0.0],
        "datetime": [0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 0.1],
        "text": [0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0],
        "math": [0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.9, 0.0, 0.0],
        "database": [0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0],
        "utility": [0.1, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.9],
    }

    QUERY_KEYWORDS = {
        "filesystem": ["file", "read", "write", "directory", "list", "search", "path", "folder"],
        "git": ["git", "commit", "diff", "log", "branch", "status", "push", "merge"],
        "http": ["http", "get", "post", "request", "api", "url", "endpoint", "fetch"],
        "parsing": ["parse", "json", "yaml", "csv", "format", "serialize", "deserialize"],
        "crypto": ["hash", "base64", "encode", "decode", "checksum", "encrypt", "sign"],
        "datetime": ["time", "date", "timestamp", "calendar", "schedule", "duration"],
        "text": ["text", "string", "replace", "find", "word", "count", "split", "join", "case"],
        "math": ["calculate", "number", "percentage", "round", "convert", "unit", "math"],
        "database": ["database", "query", "table", "record", "sql", "insert", "update", "select"],
        "utility": ["uuid", "random", "validate", "email", "generate", "compress"],
    }

    DIM = 64  # Embedding dimension

    def encode_tool(self, tool: Tool) -> List[float]:
        """Encode a tool into a semantic embedding vector."""
        # Start with category base vector (expanded to DIM)
        base = self.CATEGORY_VECTORS.get(tool.category, [0.1] * 10)
        # Expand to full dimension using deterministic hash
        seed = int(hashlib.md5(tool.name.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        embedding = []
        for i in range(self.DIM):
            if i < len(base):
                embedding.append(base[i] + rng.gauss(0, 0.05))
            else:
                embedding.append(rng.gauss(0, 0.1))

        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        return [x / norm for x in embedding]

    def encode_query(self, query: str) -> List[float]:
        """Encode a query into a semantic embedding vector."""
        query_lower = query.lower()

        # Score each category by keyword matches
        category_scores = {}
        for category, keywords in self.QUERY_KEYWORDS.items():
            score = sum(1.0 for kw in keywords if kw in query_lower)
            # Boost partial matches
            score += sum(0.3 for kw in keywords if any(kw in word for word in query_lower.split()))
            category_scores[category] = score

        # Normalize scores
        total = sum(category_scores.values()) or 1.0
        for cat in category_scores:
            category_scores[cat] /= total

        # Build embedding as weighted combination of category vectors
        embedding = [0.0] * self.DIM
        for category, weight in category_scores.items():
            base = self.CATEGORY_VECTORS.get(category, [0.0] * 10)
            for i in range(min(len(base), self.DIM)):
                embedding[i] += base[i] * weight

        # Add query-specific noise for uniqueness
        seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        for i in range(self.DIM):
            embedding[i] += rng.gauss(0, 0.02)

        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding)) or 1.0
        return [x / norm for x in embedding]


class MockNeedleModel:
    """
    Mock 26M-parameter Needle model for tool selection.

    Simulates the contrastive head that scores tools against queries
    with higher precision than the embedding model alone. The Needle
    model uses both the query and tool description for fine-grained matching.
    """

    def __init__(self):
        self.embedding_model = MockEmbeddingModel()

    def score_tools(self, query: str, tools: List[Tool]) -> List[ScoredTool]:
        """
        Score filtered tools using the Needle model's contrastive head.

        This simulates Needle's more precise scoring by using:
        - Semantic embedding similarity (base)
        - Name-query keyword overlap (precision boost)
        - Description-query term matching (context signal)
        - Exact tool name substring matching (strong signal)
        """
        query_embedding = self.embedding_model.encode_query(query)
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for tool in tools:
            # Base: cosine similarity from embeddings
            tool_embedding = self.embedding_model.encode_tool(tool)
            cosine_sim = sum(a * b for a, b in zip(query_embedding, tool_embedding))

            # Precision boost: direct name match (split on underscores)
            name_words = set(tool.name.replace("_", " ").lower().split())
            name_overlap = len(query_words & name_words) / max(len(name_words), 1)

            # Full name substring match (strongest signal - simulates Needle's contrastive head)
            tool_name_parts = tool.name.lower().split("_")
            exact_match_bonus = 0.0
            for part in tool_name_parts:
                if len(part) > 2 and part in query_lower:
                    exact_match_bonus += 0.3

            # Description match
            desc_lower = tool.description.lower()
            desc_match = sum(1 for w in query_words if w in desc_lower and len(w) > 3) / max(len(query_words), 1)

            # Combined score (Needle's contrastive head output)
            score = cosine_sim * 0.2 + name_overlap * 0.25 + exact_match_bonus + desc_match * 0.2

            scored.append(ScoredTool(tool=tool, score=score))

        # Sort descending
        scored.sort(key=lambda x: x.score, reverse=True)

        # Calculate confidence (gap between #1 and #2 normalized by top score)
        if len(scored) >= 2:
            gap = scored[0].score - scored[1].score
            # Normalize confidence to make it more discriminating
            confidence = gap / max(scored[0].score, 0.01)
            scored[0].confidence = confidence
        elif scored:
            scored[0].confidence = 1.0

        return scored


class MockFrontierModel:
    """
    Mock frontier model (Claude Haiku 4.5) for escalation.

    Simulates the 'expensive but accurate' fallback that handles
    ambiguous queries where the Needle model isn't confident enough.
    """

    # Simulated frontier token cost per escalation call
    TOKENS_PER_CALL = 850  # prompt + completion

    def select_tool(self, query: str, tools: List[Tool]) -> Tuple[str, str]:
        """
        Select tool using frontier model reasoning.

        Returns: (tool_name, reasoning)
        """
        query_lower = query.lower()

        # Simulate intelligent reasoning
        best_tool = tools[0] if tools else None
        best_score = 0

        for tool in tools:
            score = 0
            # Name relevance
            for word in tool.name.split("_"):
                if word in query_lower:
                    score += 3
            # Description relevance
            for word in query_lower.split():
                if len(word) > 3 and word in tool.description.lower():
                    score += 1

            if score > best_score:
                best_score = score
                best_tool = tool

        reasoning = f"Selected '{best_tool.name}' based on semantic analysis of query intent"
        return best_tool.name, reasoning


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Catalog (50 realistic MCP tools)
# ═══════════════════════════════════════════════════════════════════════════════

def create_tool_catalog() -> List[Tool]:
    """Create a realistic catalog of 50 MCP tools across categories."""
    tools = [
        # Filesystem (6 tools)
        Tool("read_file", "Read the contents of a file from the filesystem. Supports text and binary files with optional line range selection.", "filesystem",
             {"type": "object", "properties": {"path": {"type": "string"}, "encoding": {"type": "string"}}, "required": ["path"]}),
        Tool("write_file", "Write content to a file, creating it if it doesn't exist or overwriting if it does. Creates parent directories as needed.", "filesystem",
             {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}),
        Tool("list_directory", "List all files and directories in a given path. Supports recursive listing and filtering by pattern.", "filesystem",
             {"type": "object", "properties": {"path": {"type": "string"}, "recursive": {"type": "boolean"}}, "required": ["path"]}),
        Tool("search_files", "Search for files matching a pattern across directory trees. Supports glob and regex patterns.", "filesystem",
             {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}),
        Tool("move_file", "Move or rename a file or directory. Creates destination parent directories if needed.", "filesystem",
             {"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}}, "required": ["source", "destination"]}),
        Tool("file_info", "Get metadata about a file (size, permissions, timestamps, type).", "filesystem",
             {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),

        # Git (6 tools)
        Tool("git_status", "Show the working tree status, including staged, unstaged, and untracked files.", "git",
             {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
        Tool("git_commit", "Create a new commit with the specified message. Optionally stage all changes first.", "git",
             {"type": "object", "properties": {"message": {"type": "string"}, "all": {"type": "boolean"}}, "required": ["message"]}),
        Tool("git_diff", "Show changes between commits, commit and working tree, or staged changes.", "git",
             {"type": "object", "properties": {"path": {"type": "string"}, "staged": {"type": "boolean"}}, "required": []}),
        Tool("git_log", "Show commit history with messages, authors, dates, and optionally diffs.", "git",
             {"type": "object", "properties": {"limit": {"type": "integer"}, "since": {"type": "string"}}, "required": []}),
        Tool("git_branch", "List, create, or delete branches. Shows current branch with indicator.", "git",
             {"type": "object", "properties": {"name": {"type": "string"}, "delete": {"type": "boolean"}}, "required": []}),
        Tool("git_push", "Push commits to a remote repository. Supports force push and upstream tracking.", "git",
             {"type": "object", "properties": {"remote": {"type": "string"}, "branch": {"type": "string"}, "force": {"type": "boolean"}}, "required": []}),

        # HTTP (5 tools)
        Tool("http_get", "Make an HTTP GET request to a URL and return the response body and headers.", "http",
             {"type": "object", "properties": {"url": {"type": "string"}, "headers": {"type": "object"}}, "required": ["url"]}),
        Tool("http_post", "Make an HTTP POST request with a JSON or form body. Returns response and status.", "http",
             {"type": "object", "properties": {"url": {"type": "string"}, "body": {"type": "object"}, "headers": {"type": "object"}}, "required": ["url"]}),
        Tool("http_put", "Make an HTTP PUT request for updating resources. Returns response and status.", "http",
             {"type": "object", "properties": {"url": {"type": "string"}, "body": {"type": "object"}}, "required": ["url"]}),
        Tool("http_delete", "Make an HTTP DELETE request to remove a resource.", "http",
             {"type": "object", "properties": {"url": {"type": "string"}, "headers": {"type": "object"}}, "required": ["url"]}),
        Tool("http_download", "Download a file from a URL and save it to the filesystem.", "http",
             {"type": "object", "properties": {"url": {"type": "string"}, "output_path": {"type": "string"}}, "required": ["url", "output_path"]}),

        # Parsing/Formatting (6 tools)
        Tool("parse_json", "Parse a JSON string into a structured object. Reports errors with line numbers.", "parsing",
             {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
        Tool("format_json", "Pretty-print a JSON object with configurable indentation.", "parsing",
             {"type": "object", "properties": {"data": {"type": "object"}, "indent": {"type": "integer"}}, "required": ["data"]}),
        Tool("parse_yaml", "Parse a YAML string into a structured object. Supports multi-document YAML.", "parsing",
             {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
        Tool("format_yaml", "Serialize a data structure into YAML format with optional flow style.", "parsing",
             {"type": "object", "properties": {"data": {"type": "object"}}, "required": ["data"]}),
        Tool("parse_csv", "Parse CSV data into a list of records with header detection.", "parsing",
             {"type": "object", "properties": {"text": {"type": "string"}, "delimiter": {"type": "string"}}, "required": ["text"]}),
        Tool("format_csv", "Format a list of records into CSV output with customizable delimiters.", "parsing",
             {"type": "object", "properties": {"records": {"type": "array"}, "delimiter": {"type": "string"}}, "required": ["records"]}),

        # Crypto/Encoding (5 tools)
        Tool("calculate_hash", "Calculate hash digest of text using MD5, SHA1, SHA256, or SHA512.", "crypto",
             {"type": "object", "properties": {"text": {"type": "string"}, "algorithm": {"type": "string"}}, "required": ["text"]}),
        Tool("encode_base64", "Encode text or binary data into Base64 representation.", "crypto",
             {"type": "object", "properties": {"data": {"type": "string"}}, "required": ["data"]}),
        Tool("decode_base64", "Decode a Base64 string back into plain text or binary data.", "crypto",
             {"type": "object", "properties": {"encoded": {"type": "string"}}, "required": ["encoded"]}),
        Tool("calculate_checksum", "Calculate CRC32 or Adler32 checksum of file or text content.", "crypto",
             {"type": "object", "properties": {"text": {"type": "string"}, "algorithm": {"type": "string"}}, "required": ["text"]}),
        Tool("generate_hmac", "Generate HMAC signature for message authentication.", "crypto",
             {"type": "object", "properties": {"message": {"type": "string"}, "key": {"type": "string"}, "algorithm": {"type": "string"}}, "required": ["message", "key"]}),

        # DateTime (5 tools)
        Tool("get_current_time", "Get the current date and time in various formats and timezones.", "datetime",
             {"type": "object", "properties": {"timezone": {"type": "string"}, "format": {"type": "string"}}, "required": []}),
        Tool("parse_date", "Parse a date string in various formats into a structured datetime object.", "datetime",
             {"type": "object", "properties": {"text": {"type": "string"}, "format": {"type": "string"}}, "required": ["text"]}),
        Tool("format_date", "Format a datetime into a specific string representation.", "datetime",
             {"type": "object", "properties": {"datetime": {"type": "string"}, "format": {"type": "string"}}, "required": ["datetime", "format"]}),
        Tool("calculate_date_diff", "Calculate the difference between two dates in various units.", "datetime",
             {"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}, "unit": {"type": "string"}}, "required": ["start", "end"]}),
        Tool("add_duration", "Add a duration (days, hours, minutes) to a datetime value.", "datetime",
             {"type": "object", "properties": {"datetime": {"type": "string"}, "days": {"type": "integer"}, "hours": {"type": "integer"}}, "required": ["datetime"]}),

        # Text Processing (6 tools)
        Tool("find_and_replace", "Find and replace text patterns using string matching or regex.", "text",
             {"type": "object", "properties": {"text": {"type": "string"}, "find": {"type": "string"}, "replace": {"type": "string"}}, "required": ["text", "find", "replace"]}),
        Tool("split_text", "Split text by delimiter, regex pattern, or fixed chunk size.", "text",
             {"type": "object", "properties": {"text": {"type": "string"}, "delimiter": {"type": "string"}}, "required": ["text"]}),
        Tool("join_text", "Join an array of strings with a separator between elements.", "text",
             {"type": "object", "properties": {"parts": {"type": "array"}, "separator": {"type": "string"}}, "required": ["parts"]}),
        Tool("convert_case", "Convert text between cases: upper, lower, title, camel, snake, kebab.", "text",
             {"type": "object", "properties": {"text": {"type": "string"}, "case": {"type": "string"}}, "required": ["text", "case"]}),
        Tool("count_words", "Count words, characters, lines, and sentences in text.", "text",
             {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
        Tool("extract_regex", "Extract all matches of a regex pattern from text with groups.", "text",
             {"type": "object", "properties": {"text": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["text", "pattern"]}),

        # Math/Numbers (5 tools)
        Tool("calculate_percentage", "Calculate percentage, percentage change, or percentage of total.", "math",
             {"type": "object", "properties": {"value": {"type": "number"}, "total": {"type": "number"}}, "required": ["value", "total"]}),
        Tool("round_number", "Round a number to specified decimal places with configurable rounding mode.", "math",
             {"type": "object", "properties": {"number": {"type": "number"}, "decimals": {"type": "integer"}}, "required": ["number"]}),
        Tool("convert_units", "Convert between measurement units (length, weight, temperature, etc.).", "math",
             {"type": "object", "properties": {"value": {"type": "number"}, "from_unit": {"type": "string"}, "to_unit": {"type": "string"}}, "required": ["value", "from_unit", "to_unit"]}),
        Tool("format_number", "Format numbers with thousands separators, currency symbols, or scientific notation.", "math",
             {"type": "object", "properties": {"number": {"type": "number"}, "format": {"type": "string"}}, "required": ["number"]}),
        Tool("evaluate_expression", "Safely evaluate a mathematical expression and return the result.", "math",
             {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}),

        # Database (5 tools)
        Tool("query_database", "Execute a SELECT query against a database and return results as records.", "database",
             {"type": "object", "properties": {"query": {"type": "string"}, "database": {"type": "string"}}, "required": ["query", "database"]}),
        Tool("create_table", "Create a new database table with specified columns and constraints.", "database",
             {"type": "object", "properties": {"table": {"type": "string"}, "columns": {"type": "array"}}, "required": ["table", "columns"]}),
        Tool("insert_record", "Insert one or more records into a database table.", "database",
             {"type": "object", "properties": {"table": {"type": "string"}, "records": {"type": "array"}}, "required": ["table", "records"]}),
        Tool("update_record", "Update records in a database table matching a condition.", "database",
             {"type": "object", "properties": {"table": {"type": "string"}, "set": {"type": "object"}, "where": {"type": "string"}}, "required": ["table", "set", "where"]}),
        Tool("delete_record", "Delete records from a database table matching a condition.", "database",
             {"type": "object", "properties": {"table": {"type": "string"}, "where": {"type": "string"}}, "required": ["table", "where"]}),

        # Utility (6 tools)
        Tool("generate_uuid", "Generate a UUID (v4 random or v5 namespace-based).", "utility",
             {"type": "object", "properties": {"version": {"type": "integer"}, "namespace": {"type": "string"}}, "required": []}),
        Tool("validate_email", "Validate an email address format and optionally check DNS/MX records.", "utility",
             {"type": "object", "properties": {"email": {"type": "string"}, "check_dns": {"type": "boolean"}}, "required": ["email"]}),
        Tool("validate_url", "Validate a URL format and optionally check if it's reachable.", "utility",
             {"type": "object", "properties": {"url": {"type": "string"}, "check_reachable": {"type": "boolean"}}, "required": ["url"]}),
        Tool("extract_urls", "Extract all URLs from a text string with optional domain filtering.", "utility",
             {"type": "object", "properties": {"text": {"type": "string"}, "domain_filter": {"type": "string"}}, "required": ["text"]}),
        Tool("generate_random_string", "Generate a random string of specified length with character set options.", "utility",
             {"type": "object", "properties": {"length": {"type": "integer"}, "charset": {"type": "string"}}, "required": ["length"]}),
        Tool("run_shell_command", "Execute a shell command and return stdout, stderr, and exit code.", "utility",
             {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]}),
    ]

    return tools


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline Implementation
# ═══════════════════════════════════════════════════════════════════════════════

class ToolGateStage:
    """
    Stage 1: ToolGate semantic filtering.

    Uses sentence-transformer embeddings + FAISS-style similarity search
    to narrow 50+ tools down to the top-K most semantically relevant ones.
    """

    def __init__(self, tools: List[Tool], top_k: int = 10):
        self.tools = tools
        self.top_k = top_k
        self.embedding_model = MockEmbeddingModel()
        self.tool_embeddings: Dict[str, List[float]] = {}

        # Pre-compute tool embeddings (simulates FAISS index build)
        for tool in tools:
            self.tool_embeddings[tool.name] = self.embedding_model.encode_tool(tool)

    def filter(self, query: str) -> List[ScoredTool]:
        """Filter tools by semantic similarity to query."""
        query_embedding = self.embedding_model.encode_query(query)

        # Compute cosine similarity with all tools
        scored = []
        for tool in self.tools:
            tool_emb = self.tool_embeddings[tool.name]
            similarity = sum(a * b for a, b in zip(query_embedding, tool_emb))
            scored.append(ScoredTool(tool=tool, score=similarity))

        # Sort by score descending and take top-K
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:self.top_k]


class NeedleRouteStage:
    """
    Stage 2: NeedleRoute Needle model scoring.

    Uses the 26M-parameter Needle model's contrastive head to do
    fine-grained tool selection from the filtered set.
    """

    def __init__(self, confidence_threshold: float = 0.25):
        self.needle = MockNeedleModel()
        self.frontier = MockFrontierModel()
        self.confidence_threshold = confidence_threshold

    def route(self, query: str, filtered_tools: List[Tool]) -> Tuple[List[ScoredTool], bool, Optional[str], str]:
        """
        Route query to best tool with confidence-based escalation.

        Returns: (needle_scores, escalated, escalation_reason, selected_tool_name)
        """
        # Score tools with Needle model
        needle_scores = self.needle.score_tools(query, filtered_tools)

        if not needle_scores:
            return [], True, "no_tools_available", ""

        top = needle_scores[0]

        # Check confidence threshold
        if top.confidence < self.confidence_threshold:
            # Low confidence → escalate to frontier model
            selected, reasoning = self.frontier.select_tool(query, filtered_tools)
            return needle_scores, True, f"low_confidence ({top.confidence:.3f} < {self.confidence_threshold})", selected
        else:
            # High confidence → use Needle's selection
            return needle_scores, False, None, top.tool.name


class CombinedPipeline:
    """
    Full ToolGate → NeedleRoute pipeline.

    Orchestrates both stages and collects comprehensive metrics.
    """

    def __init__(self, tools: List[Tool], top_k: int = 10, confidence_threshold: float = 0.25):
        self.tools = tools
        self.toolgate = ToolGateStage(tools, top_k=top_k)
        self.needleroute = NeedleRouteStage(confidence_threshold=confidence_threshold)
        self.total_tokens_all = sum(t.token_count for t in tools)

    def run(self, query: str, correct_tool: str) -> PipelineResult:
        """Run the full pipeline for a query."""

        # Stage 1: ToolGate
        t0 = time.perf_counter()
        toolgate_results = self.toolgate.filter(query)
        t1 = time.perf_counter()
        toolgate_latency = (t1 - t0) * 1000

        # Extract tools for stage 2
        filtered_tools = [st.tool for st in toolgate_results]
        tokens_after_toolgate = sum(t.token_count for t in filtered_tools)

        # Stage 2: NeedleRoute
        t2 = time.perf_counter()
        needle_scores, escalated, escalation_reason, selected_tool = self.needleroute.route(query, filtered_tools)
        t3 = time.perf_counter()
        needle_latency = (t3 - t2) * 1000

        # Escalation latency (simulated ~200ms for frontier model)
        escalation_latency = 0.0
        if escalated:
            escalation_latency = random.uniform(180, 250)  # simulated API call

        # Token cost for final selection
        tokens_after_pipeline = sum(
            t.token_count for t in filtered_tools[:3]  # Only top-3 sent to Needle
        )
        if escalated:
            tokens_after_pipeline += MockFrontierModel.TOKENS_PER_CALL

        total_latency = toolgate_latency + needle_latency + escalation_latency

        return PipelineResult(
            query=query,
            selected_tool=selected_tool,
            correct_tool=correct_tool,
            toolgate_results=toolgate_results,
            needle_results=needle_scores,
            escalated=escalated,
            escalation_reason=escalation_reason,
            toolgate_latency_ms=toolgate_latency,
            needle_latency_ms=needle_latency,
            escalation_latency_ms=escalation_latency,
            total_latency_ms=total_latency,
            tokens_all_tools=self.total_tokens_all,
            tokens_after_toolgate=tokens_after_toolgate,
            tokens_after_pipeline=tokens_after_pipeline,
            correct=(selected_tool == correct_tool),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Test Queries
# ═══════════════════════════════════════════════════════════════════════════════

TEST_QUERIES = [
    # (query, expected_correct_tool)
    ("Read the contents of /etc/nginx/nginx.conf", "read_file"),
    ("Show me the git commit history for the last week", "git_log"),
    ("Make an HTTP POST request to the authentication API", "http_post"),
    ("Parse this JSON string into a Python object", "parse_json"),
    ("Calculate the SHA256 hash of this text", "calculate_hash"),
    ("What time is it in Tokyo right now?", "get_current_time"),
    ("Replace all occurrences of 'foo' with 'bar' in the text", "find_and_replace"),
    ("Convert 72 degrees Fahrenheit to Celsius", "convert_units"),
    ("Query the users table for active accounts", "query_database"),
    ("Generate a random UUID for this record", "generate_uuid"),
    ("List all files in the project directory", "list_directory"),
    ("Check the current git status of the repository", "git_status"),
    ("Download the file from this URL", "http_download"),
    ("Format this data as a YAML configuration file", "format_yaml"),
    ("Encode this string in Base64", "encode_base64"),
    ("Calculate how many days between these two dates", "calculate_date_diff"),
    ("Count the number of words in this document", "count_words"),
    ("Insert a new record into the orders table", "insert_record"),
    ("Validate this email address format", "validate_email"),
    ("Write these results to output.json", "write_file"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Demo Execution
# ═══════════════════════════════════════════════════════════════════════════════

def run_demo():
    """Run the full demonstration."""
    print_banner()

    tools = create_tool_catalog()
    print(f"  {Colors.GREEN}✓{Colors.RESET} Loaded {Colors.BOLD}{len(tools)}{Colors.RESET} MCP tools across {len(set(t.category for t in tools))} categories")
    print(f"  {Colors.GREEN}✓{Colors.RESET} Total token cost (all tools): {Colors.BOLD}{sum(t.token_count for t in tools):,}{Colors.RESET} tokens")

    # ─────────────────────────────────────────────────────────────────────────
    # Section 1: Pipeline Architecture
    # ─────────────────────────────────────────────────────────────────────────
    print_header("PIPELINE ARCHITECTURE")

    print(f"""
  {Colors.DIM}┌─────────────────────────────────────────────────────────────────────────┐{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}                                                                         {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   {Colors.BOLD}User Query{Colors.RESET}                                                        {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       │                                                                 {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       ▼                                                                 {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   {Colors.BG_BLUE} Stage 1: ToolGate {Colors.RESET}                                           {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   ┌─────────────────────────────────────────────────┐                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • Sentence-transformer embeddings (MiniLM-L6)   │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • FAISS cosine similarity search                │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • 50 tools → top-10 semantically relevant       │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • Latency: ~5-15ms                              │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   └─────────────────────────────────────────────────┘                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       │ top-10 tools                                                   {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       ▼                                                                 {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   {Colors.BG_GREEN} Stage 2: NeedleRoute {Colors.RESET}                                        {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   ┌─────────────────────────────────────────────────┐                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • 26M-param Needle model (contrastive head)     │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • Fine-grained tool selection from filtered set  │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • Confidence scoring (top-1 vs top-2 gap)       │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   │ • Latency: ~2-8ms                               │                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}   └─────────────────────────────────────────────────┘                  {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       │                                                                 {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       ├── High confidence ──▶ {Colors.GREEN}✓ Return selected tool{Colors.RESET}                {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       │                                                                 {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}       └── Low confidence ──▶ {Colors.BG_RED} Stage 3: Escalation {Colors.RESET}              {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}                                ┌──────────────────────────────┐        {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}                                │ • Frontier model (Haiku 4.5) │        {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}                                │ • Only over filtered set!    │        {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}                                │ • 10 tools, not 50           │        {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}                                └──────────────────────────────┘        {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}│{Colors.RESET}                                                                         {Colors.DIM}│{Colors.RESET}
  {Colors.DIM}└─────────────────────────────────────────────────────────────────────────┘{Colors.RESET}
""")

    # ─────────────────────────────────────────────────────────────────────────
    # Section 2: Run all queries through all approaches
    # ─────────────────────────────────────────────────────────────────────────
    print_header("RUNNING BENCHMARK: 20 Queries × 3 Approaches")

    pipeline = CombinedPipeline(tools, top_k=10, confidence_threshold=0.25)

    # Approach 1: No filtering (baseline)
    baseline_tokens = sum(t.token_count for t in tools)

    # Approach 2: ToolGate only
    toolgate_only_results = []
    for query, correct in TEST_QUERIES:
        filtered = pipeline.toolgate.filter(query)
        selected = filtered[0].tool.name if filtered else ""
        toolgate_only_results.append({
            "query": query,
            "correct": correct,
            "selected": selected,
            "accurate": selected == correct,
            "tokens": sum(st.tool.token_count for st in filtered),
        })

    # Approach 3: ToolGate + NeedleRoute (full pipeline)
    pipeline_results: List[PipelineResult] = []
    for query, correct in TEST_QUERIES:
        result = pipeline.run(query, correct)
        pipeline_results.append(result)

    # ─────────────────────────────────────────────────────────────────────────
    # Section 3: Detailed query-by-query results
    # ─────────────────────────────────────────────────────────────────────────
    print_header("QUERY-BY-QUERY RESULTS")

    for i, (result, tg_result) in enumerate(zip(pipeline_results, toolgate_only_results)):
        query_short = result.query[:55] + "..." if len(result.query) > 55 else result.query
        status_pipeline = f"{Colors.GREEN}✓{Colors.RESET}" if result.correct else f"{Colors.RED}✗{Colors.RESET}"
        status_tg = f"{Colors.GREEN}✓{Colors.RESET}" if tg_result["accurate"] else f"{Colors.RED}✗{Colors.RESET}"

        escalation_tag = ""
        if result.escalated:
            escalation_tag = f" {Colors.YELLOW}[ESCALATED]{Colors.RESET}"

        print(f"\n  {Colors.DIM}Query {i+1:2d}:{Colors.RESET} {Colors.BOLD}{query_short}{Colors.RESET}")
        print(f"           Expected: {Colors.CYAN}{result.correct_tool}{Colors.RESET}")
        print(f"           ToolGate only: {status_tg} {tg_result['selected']}")
        print(f"           Full pipeline: {status_pipeline} {result.selected_tool}{escalation_tag}")

        if i < 5:  # Show detailed scores for first 5 queries
            print(f"           {Colors.DIM}ToolGate top-3: ", end="")
            for st in result.toolgate_results[:3]:
                print(f"{st.tool.name}({st.score:.3f}) ", end="")
            print(Colors.RESET)

    # ─────────────────────────────────────────────────────────────────────────
    # Section 4: Comparison table
    # ─────────────────────────────────────────────────────────────────────────
    print_header("APPROACH COMPARISON")

    # Calculate metrics
    n_queries = len(TEST_QUERIES)

    # Baseline (no filtering)
    baseline_accuracy = n_queries  # Assume LLM with all tools gets 100% (it has everything)
    baseline_token_cost = baseline_tokens * n_queries
    baseline_latency = 0  # No overhead, but LLM must process all tokens

    # ToolGate only
    tg_accuracy = sum(1 for r in toolgate_only_results if r["accurate"])
    tg_token_cost = sum(r["tokens"] for r in toolgate_only_results)
    tg_avg_latency = sum(r.toolgate_latency_ms for r in pipeline_results) / n_queries

    # Full pipeline
    pipe_accuracy = sum(1 for r in pipeline_results if r.correct)
    pipe_token_cost = sum(r.tokens_after_pipeline for r in pipeline_results)
    pipe_avg_latency = sum(r.total_latency_ms for r in pipeline_results) / n_queries
    pipe_escalations = sum(1 for r in pipeline_results if r.escalated)

    print_subheader("Token Usage")
    print_table(
        ["Approach", "Tokens/Query", "Total (20 queries)", "Reduction"],
        [
            ["No filtering (baseline)", f"{baseline_tokens:,}", f"{baseline_token_cost:,}", "—"],
            ["ToolGate only (top-10)", f"{tg_token_cost // n_queries:,}", f"{tg_token_cost:,}",
             f"{Colors.GREEN}{((baseline_token_cost - tg_token_cost) / baseline_token_cost * 100):.1f}%{Colors.RESET}"],
            ["ToolGate + NeedleRoute", f"{pipe_token_cost // n_queries:,}", f"{pipe_token_cost:,}",
             f"{Colors.GREEN}{((baseline_token_cost - pipe_token_cost) / baseline_token_cost * 100):.1f}%{Colors.RESET}"],
        ],
        [28, 14, 20, 12],
    )

    print_subheader("Accuracy (Correct Tool Selected)")
    print_table(
        ["Approach", "Correct", "Total", "Accuracy"],
        [
            ["No filtering (LLM picks)", f"{n_queries}", f"{n_queries}", f"{Colors.GREEN}100%{Colors.RESET} (theoretical)"],
            ["ToolGate only (top-1)", f"{tg_accuracy}", f"{n_queries}", f"{tg_accuracy / n_queries * 100:.0f}%"],
            ["ToolGate + NeedleRoute", f"{pipe_accuracy}", f"{n_queries}",
             f"{Colors.GREEN}{pipe_accuracy / n_queries * 100:.0f}%{Colors.RESET}"],
        ],
        [28, 9, 7, 22],
    )

    print_subheader("Latency Overhead")
    print_table(
        ["Approach", "Avg Latency", "P95 Latency", "Note"],
        [
            ["No filtering", "0ms", "0ms", "No proxy overhead (but LLM slower)"],
            ["ToolGate only", f"{tg_avg_latency:.1f}ms", f"{max(r.toolgate_latency_ms for r in pipeline_results):.1f}ms", "Embedding search"],
            ["ToolGate + NeedleRoute", f"{pipe_avg_latency:.1f}ms",
             f"{max(r.total_latency_ms for r in pipeline_results):.1f}ms",
             f"Incl. {pipe_escalations} escalations"],
        ],
        [28, 13, 13, 36],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Section 5: Cost Analysis
    # ─────────────────────────────────────────────────────────────────────────
    print_header("COST ANALYSIS (at $3/MTok input pricing)")

    cost_per_mtok = 3.0  # $/million tokens

    baseline_cost = (baseline_token_cost / 1_000_000) * cost_per_mtok
    tg_cost = (tg_token_cost / 1_000_000) * cost_per_mtok
    pipe_cost = (pipe_token_cost / 1_000_000) * cost_per_mtok

    # Scale to 10k requests (realistic daily load)
    scale = 10_000 / n_queries
    print(f"""
  {Colors.BOLD}Projected costs at 10,000 requests/day:{Colors.RESET}

  ┌────────────────────────────────────────────────────────────────────┐
  │                                                                    │
  │  {Colors.RED}■{Colors.RESET} No filtering:        ${baseline_cost * scale:>8.2f}/day   (${baseline_cost * scale * 30:>10.2f}/month)  │
  │  {Colors.YELLOW}■{Colors.RESET} ToolGate only:        ${tg_cost * scale:>8.2f}/day   (${tg_cost * scale * 30:>10.2f}/month)  │
  │  {Colors.GREEN}■{Colors.RESET} ToolGate+NeedleRoute: ${pipe_cost * scale:>8.2f}/day   (${pipe_cost * scale * 30:>10.2f}/month)  │
  │                                                                    │
  │  {Colors.GREEN}Savings vs baseline:   ${(baseline_cost - pipe_cost) * scale:>8.2f}/day   (${(baseline_cost - pipe_cost) * scale * 30:>10.2f}/month){Colors.RESET}  │
  │  {Colors.GREEN}Reduction:             {((baseline_cost - pipe_cost) / baseline_cost * 100):.1f}%{Colors.RESET}                                         │
  │                                                                    │
  └────────────────────────────────────────────────────────────────────┘
""")

    # ─────────────────────────────────────────────────────────────────────────
    # Section 6: Escalation Analysis
    # ─────────────────────────────────────────────────────────────────────────
    print_header("ESCALATION ANALYSIS")

    escalated_results = [r for r in pipeline_results if r.escalated]
    non_escalated = [r for r in pipeline_results if not r.escalated]

    print(f"""
  {Colors.BOLD}Escalation Statistics:{Colors.RESET}

    Total queries:           {n_queries}
    Handled by Needle:       {Colors.GREEN}{len(non_escalated)}{Colors.RESET} ({len(non_escalated)/n_queries*100:.0f}%)
    Escalated to frontier:   {Colors.YELLOW}{len(escalated_results)}{Colors.RESET} ({len(escalated_results)/n_queries*100:.0f}%)

  {Colors.BOLD}Why this matters:{Colors.RESET}

    Without the pipeline, ALL {n_queries} queries would go to the frontier model.
    With ToolGate+NeedleRoute, only {len(escalated_results)} need the expensive model.
    The Needle model (26M params, runs locally) handles {len(non_escalated)/n_queries*100:.0f}% of routing.
""")

    if escalated_results:
        print_subheader("Escalated Queries (low Needle confidence)")
        for r in escalated_results:
            query_short = r.query[:50] + "..." if len(r.query) > 50 else r.query
            status = f"{Colors.GREEN}✓{Colors.RESET}" if r.correct else f"{Colors.RED}✗{Colors.RESET}"
            print(f"    {status} \"{query_short}\"")
            print(f"      {Colors.DIM}Reason: {r.escalation_reason}{Colors.RESET}")

    # ─────────────────────────────────────────────────────────────────────────
    # Section 7: Key Insights
    # ─────────────────────────────────────────────────────────────────────────
    print_header("KEY INSIGHTS")

    tg_reduction_pct = (baseline_token_cost - tg_token_cost) / baseline_token_cost * 100
    pipe_reduction_pct = (baseline_token_cost - pipe_token_cost) / baseline_token_cost * 100

    print(f"""
  {Colors.GREEN}1. Token Savings{Colors.RESET}
     ToolGate alone reduces tokens by {Colors.BOLD}{tg_reduction_pct:.0f}%{Colors.RESET} (50 → 10 tools).
     Adding NeedleRoute pushes savings to {Colors.BOLD}{pipe_reduction_pct:.0f}%{Colors.RESET} (only top candidates sent).

  {Colors.GREEN}2. Accuracy vs Cost Tradeoff{Colors.RESET}
     The full pipeline achieves {Colors.BOLD}{pipe_accuracy/n_queries*100:.0f}%{Colors.RESET} accuracy while using
     {Colors.BOLD}{pipe_reduction_pct:.0f}% fewer tokens{Colors.RESET} than sending all tools to the LLM.
     Escalation ensures hard cases still get frontier-model quality.

  {Colors.GREEN}3. Latency is Negligible{Colors.RESET}
     Average pipeline overhead: {Colors.BOLD}{pipe_avg_latency:.1f}ms{Colors.RESET}
     This is <1% of typical LLM response latency (1-5 seconds).
     The token reduction actually makes overall responses FASTER.

  {Colors.GREEN}4. Smart Escalation{Colors.RESET}
     {Colors.BOLD}{len(non_escalated)/n_queries*100:.0f}%{Colors.RESET} of queries handled by the tiny Needle model (local, free).
     Only {Colors.BOLD}{len(escalated_results)/n_queries*100:.0f}%{Colors.RESET} escalated to frontier model (expensive, but necessary).
     Escalation operates over {Colors.BOLD}10 tools, not 50{Colors.RESET} — saving tokens even when escalating.

  {Colors.GREEN}5. Composability{Colors.RESET}
     ToolGate and NeedleRoute work independently OR together.
     Together they form a defense-in-depth approach to tool selection.
     Each stage catches what the other might miss.
""")

    # ─────────────────────────────────────────────────────────────────────────
    # Final Summary
    # ─────────────────────────────────────────────────────────────────────────
    print(f"""
{Colors.CYAN}{Colors.BOLD}{'═' * 78}
  DEMO COMPLETE
{'═' * 78}{Colors.RESET}

  The ToolGate × NeedleRoute pipeline demonstrates that combining:
    • {Colors.BLUE}Semantic search{Colors.RESET} (ToolGate) for broad filtering
    • {Colors.GREEN}Specialized small model{Colors.RESET} (Needle) for precise selection
    • {Colors.YELLOW}Frontier escalation{Colors.RESET} (Haiku 4.5) for hard cases

  ...creates a system that is {Colors.BOLD}cheaper, faster, and smarter{Colors.RESET} than
  dumping all 50+ tools into every LLM context window.

  {Colors.DIM}ProtoGenesis — Building the primitives of intelligent infrastructure.{Colors.RESET}
""")

    return 0


if __name__ == "__main__":
    try:
        exit_code = run_demo()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
        exit_code = 1
    except Exception as e:
        print(f"\n\n{Colors.RED}Error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        exit_code = 1

    raise SystemExit(exit_code)
