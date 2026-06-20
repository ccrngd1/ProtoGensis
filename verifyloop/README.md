# VerifyLoop

**Generate typed guard surfaces from YAML specs and wire them into a deterministic verification loop for AI coding agents.**

VerifyLoop transforms security invariants from "the AI should remember to check auth" into "the AI literally cannot generate code that skips auth — it does not compile."

## The Problem

AI coding agents are powerful but probabilistic. When generating code, they might:
- Skip authentication checks
- Forget input validation
- Bypass authorization layers
- Access databases directly without proper guards

Traditional approaches rely on:
1. **Prompting**: "Remember to validate input" → unreliable
2. **Post-hoc testing**: Runtime tests catch errors late → expensive
3. **Code review**: Human review catches issues → slow, inconsistent

## The Solution

VerifyLoop makes security invariants **physically unbreakable** at compile time using TypeScript's type system:

1. **Define invariants** in a YAML spec (e.g., multi-tenant auth chain)
2. **Generate branded types** that enforce the chain at compile time
3. **Protect critical functions** so they only accept fully validated inputs
4. **Run verification loops** that give AI agents structured feedback

The result: **insecure code becomes a compile error**, not a runtime bug.

## Quick Start

### Installation

```bash
npm install verifyloop
# or
yarn add verifyloop
# or
pnpm add verifyloop
```

### 1. Write a Spec

Create `verifyloop.spec.yaml`:

```yaml
version: "1.0"

invariants:
  - name: multi-tenant-auth
    description: "Ensures all DB queries are validated, authenticated, and authorized"

    chain:
      - type: RawInput
        description: "Unvalidated user input"
        constructor: createRawInput
        fields:
          data: unknown

      - type: ValidatedInput
        description: "Input validated against schema"
        constructor: validateInput
        requires: RawInput
        fields:
          userId: string
          action: string

      - type: AuthenticatedCtx
        description: "User authenticated with valid token"
        constructor: authenticate
        requires: ValidatedInput
        fields:
          userId: string
          action: string
          token: string

      - type: AuthorizedQuery
        description: "Request authorized for specific tenant"
        constructor: authorizeQuery
        requires: AuthenticatedCtx
        fields:
          userId: string
          action: string
          token: string
          tenantId: string

    protected_functions:
      - dbQuery
      - dbWrite
      - dbDelete

    settings:
      max_retries: 5
      error_budget: increasing
      brand_style: symbol
```

### 2. Generate Guards

```bash
verifyloop generate --spec verifyloop.spec.yaml --output ./guards
```

This creates:
- `guards/multi-tenant-auth.d.ts` - Branded type declarations
- `guards/multi-tenant-auth.ts` - Constructor stubs and protected functions
- `guards/index.ts` - Barrel export

### 3. Implement Constructor Logic

Fill in `guards/multi-tenant-auth.ts`:

```typescript
export function validateInput(input: RawInput): ValidatedInput {
  // Add your validation logic
  const data = input.data as { userId: string; action: string };

  if (!data.userId || !data.action) {
    throw new Error('Invalid input');
  }

  return {
    userId: data.userId,
    action: data.action,
  } as ValidatedInput;
}

export function authenticate(input: ValidatedInput, token: string): AuthenticatedCtx {
  // Verify JWT, check session, etc.
  if (!verifyToken(token)) {
    throw new Error('Authentication failed');
  }

  return {
    ...input,
    token,
  } as AuthenticatedCtx;
}

// ... implement other constructors
```

### 4. Write Code That Enforces the Invariant

```typescript
import {
  createRawInput,
  validateInput,
  authenticate,
  authorizeQuery,
  dbQuery,
} from './guards/multi-tenant-auth';

export async function getUserData(req: Request, res: Response) {
  // Step through the full chain
  const raw = createRawInput(req.body);
  const validated = validateInput(raw);
  const authed = authenticate(validated, req.headers.authorization);
  const authorized = authorizeQuery(authed, req.headers['x-tenant-id']);

  // Now we can call the protected function
  const data = await dbQuery(authorized);

  res.json(data);
}
```

**Try to skip a step:**

```typescript
// This will NOT compile:
const data = await dbQuery(req.body);
//                          ^^^^^^^^
// Error: Argument of type 'unknown' is not assignable to parameter of type 'AuthorizedQuery'
```

### 5. Run Verification

```bash
# Check a file or directory
verifyloop check ./src --spec verifyloop.spec.yaml

# Run verification loop with retries
verifyloop loop --path ./src --spec verifyloop.spec.yaml --max-retries 5
```

## Spec Format Reference

### Version

```yaml
version: "1.0"
```

Required. Specifies the spec version.

### Invariants

Each invariant defines a security rule enforced by a type chain.

```yaml
invariants:
  - name: invariant-name          # Unique identifier
    description: "Description"    # Human-readable explanation

    chain:                        # Ordered list of types
      - type: TypeName
        constructor: functionName
        description: "What this step does"
        requires: PreviousType   # Optional: input type
        fields:                   # Optional: type fields
          field1: string
          field2: number

    protected_functions:          # Functions that require final type
      - functionName1
      - functionName2

    settings:                     # Optional settings
      max_retries: 5
      error_budget: increasing    # increasing|decreasing|none
      brand_style: symbol         # symbol|class|zod (v1: symbol only)
```

### Chain Steps

Each step in the chain defines a type and its constructor:

- **type**: The TypeScript type name (e.g., `ValidatedInput`)
- **constructor**: Function that creates this type (e.g., `validateInput`)
- **description**: Explains what this step does
- **requires**: (Optional) The input type from the previous step
- **fields**: (Optional) Fields for this type

### Protected Functions

Functions listed here can ONLY be called with the final type in the chain. TypeScript enforces this at compile time.

### Settings

- **max_retries**: Maximum retry attempts in loop mode (default: 5)
- **error_budget**: Abort strategy
  - `increasing`: Abort if errors increase
  - `decreasing`: Abort if errors don't decrease
  - `none`: Never abort based on error count
- **brand_style**: Branding technique (v1 supports `symbol` only)

## CLI Reference

### `verifyloop generate`

Generate guard files from spec.

```bash
verifyloop generate [options]

Options:
  -s, --spec <path>     Path to spec file (default: verifyloop.spec.yaml)
  -o, --output <path>   Output directory (default: ./guards)
```

### `verifyloop check`

Run verification on target path.

```bash
verifyloop check <path> [options]

Arguments:
  path                  File or directory to verify

Options:
  -s, --spec <path>     Path to spec file (default: verifyloop.spec.yaml)
  -t, --tsconfig <path> Path to tsconfig.json
```

### `verifyloop loop`

Run verification loop with retries.

```bash
verifyloop loop [options]

Options:
  -p, --path <path>           Target path to verify (required)
  -s, --spec <path>           Path to spec file (default: verifyloop.spec.yaml)
  -m, --max-retries <number>  Max retries (default: 5)
  -e, --error-budget <strategy> Error budget (increasing|decreasing|none, default: none)
  -t, --tsconfig <path>       Path to tsconfig.json
  -w, --watch                 Watch mode (re-run on changes)
```

## MCP Tool Reference

VerifyLoop provides a Model Context Protocol (MCP) server for AI agents.

### Start the MCP Server

```bash
npx verifyloop-mcp
```

### Available Tools

#### `verify_code`

Verify code against spec. Returns PASS or structured errors.

```json
{
  "name": "verify_code",
  "arguments": {
    "path": "./src/api.ts",
    "spec": "verifyloop.spec.yaml",
    "tsconfig": "tsconfig.json"
  }
}
```

Response:

```json
{
  "success": false,
  "errors": [
    {
      "file": "src/api.ts",
      "line": 42,
      "invariant": "multi-tenant-auth",
      "violation": "Type 'unknown' is not assignable to 'AuthorizedQuery'",
      "hint": "Use createRawInput(validateInput(authenticate(authorizeQuery(input)))) to construct AuthorizedQuery",
      "is_guard_related": true
    }
  ],
  "warnings": []
}
```

#### `generate_guards`

Generate or regenerate guard files.

```json
{
  "name": "generate_guards",
  "arguments": {
    "spec": "verifyloop.spec.yaml",
    "output": "./guards"
  }
}
```

#### `verify_loop_status`

Get current retry count and error history.

```json
{
  "name": "verify_loop_status",
  "arguments": {}
}
```

## How It Differs

### vs. Kiro (AWS)

**Kiro**: Probabilistic verification using LLMs to check behavioral properties at runtime.

**VerifyLoop**: Deterministic verification using TypeScript's type system at compile time.

- Kiro uses AI to verify behavior → can miss edge cases
- VerifyLoop uses types to verify structure → mathematically guaranteed

### vs. Forge

**Forge**: Constraint-based verification for behavioral properties (test coverage, error handling).

**VerifyLoop**: Type-level verification for structural properties (data flow, access control).

- Forge checks "does this function handle errors?" → behavioral
- VerifyLoop checks "does this data flow through auth?" → structural

Both are complementary. Use VerifyLoop for data flow invariants, Forge for behavioral constraints.

## Demo Walkthrough

See the [demo directory](./demo) for a complete multi-tenant authentication example:

1. **Without guards** - Vulnerable code that compiles but is insecure
2. **With guards (wrong)** - AI-generated code that skips auth → compile error
3. **With guards (correct)** - Code that follows the chain → compiles successfully

Run the demo:

```bash
cd demo

# Generate guards
verifyloop generate --spec verifyloop.spec.yaml --output ./with-guards/guards

# Try the bad code (will fail)
verifyloop check ./with-guards/bad-api.ts --spec verifyloop.spec.yaml

# Try the correct code (will pass)
verifyloop check ./with-guards/correct-api.ts --spec verifyloop.spec.yaml
```

## Architecture

```
Spec File (YAML) → Guard Generator → .d.ts files + constructors
                                           ↓
Agent writes code → tsc --noEmit → PASS → Accept
                          ↓ FAIL
               Structured error feedback → Agent retry (max 5)
```

### Components

1. **Spec Parser** - Reads and validates YAML specs
2. **Guard Generator** - Generates branded TypeScript types
3. **Verification Gate** - Runs `tsc --noEmit` and parses errors
4. **Loop Runner** - Orchestrates retry cycles with error budget
5. **CLI** - Command-line interface
6. **MCP Server** - Model Context Protocol integration

## TypeScript Integration

VerifyLoop uses **branded types** with unique symbols:

```typescript
declare const __brand: unique symbol;
type Brand<T, TBrand extends string> = T & { readonly [__brand]: TBrand };

export type AuthorizedQuery = Brand<{
  userId: string;
  tenantId: string;
}, 'AuthorizedQuery'>;
```

This ensures:
- Zero runtime overhead (types erased at compile time)
- Structural type safety (cannot bypass with `as`)
- Clear error messages (TypeScript knows exactly what's wrong)

## Error Feedback

When verification fails, VerifyLoop provides structured feedback:

```json
{
  "file": "src/handlers/users.ts",
  "line": 42,
  "column": 15,
  "invariant": "multi-tenant-auth",
  "violation": "Function dbQuery requires AuthorizedQuery but received RawInput",
  "hint": "Use authorizeQuery(authenticate(validateInput(input))) to construct AuthorizedQuery",
  "guard_definition": "Guard: multi-tenant-auth\nChain: RawInput → ValidatedInput → AuthenticatedCtx → AuthorizedQuery",
  "is_guard_related": true
}
```

## Contributing

VerifyLoop is built with TypeScript and uses:
- Node.js 20+
- TypeScript 5.4+
- Vitest for testing
- tsup for building

```bash
# Install dependencies
npm install

# Build
npm run build

# Test
npm test

# Run in dev mode
npm run dev
```

## License

MIT

## Citation

If you use VerifyLoop in research, please cite:

- Forge: [github.com/antoinezambelli/forge](https://github.com/antoinezambelli/forge) - Constraint-based verification, 8B model 53% → 99%
- LangChain compiler feedback: [aipatternbook.com/shift-left-feedback](https://aipatternbook.com/shift-left-feedback) - 52.8% → 66.5% on TerminalBench 2.0
- AWS Kiro: Formal spec verification for AI agents
- Shen-Backpressure: [reubenbrooks.dev](https://reubenbrooks.dev) - Structured feedback loops (115 HN pts, May 2026)
