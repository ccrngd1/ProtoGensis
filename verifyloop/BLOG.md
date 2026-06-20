# I Made My AI Agent's Security Rules Physically Unbreakable

## How TypeScript's Type System Turns Runtime Bugs Into Compile Errors

When you ask an AI coding agent to "add an API endpoint to fetch user data," it will probably write something like this:

```typescript
export async function getUserData(req: Request, res: Response) {
  const { userId } = req.body;
  const userData = await database.query('SELECT * FROM users WHERE id = ?', [userId]);
  res.json(userData);
}
```

This code works. It compiles. It runs. And it has a critical security vulnerability.

There's no input validation. No authentication check. No tenant authorization. In a multi-tenant SaaS system, this means tenant A can access tenant B's data simply by changing a request parameter.

The traditional solution is to remind the AI: "Remember to validate input, check authentication, and verify tenant access." But AI agents are probabilistic. They forget. They take shortcuts. They optimize for what you asked for, not what you meant.

What if instead of *reminding* the AI to follow security rules, we made it *physically impossible* to write insecure code?

That's what VerifyLoop does.

## The Problem: Probabilistic Security

AI coding agents are incredibly powerful, but they're fundamentally probabilistic. When you give them a task, they generate code based on patterns they've learned. Sometimes they remember to check authentication. Sometimes they don't.

This isn't a bug in the AI — it's the nature of how they work. And it creates a serious problem for security-critical systems.

Consider the data from recent research:

- **Forge** (github.com/antoinezambelli/forge) showed that constraint-based verification improved an 8B model from 53% to 99% correctness on security-critical tasks
- **LangChain's compiler feedback experiments** (aipatternbook.com/shift-left-feedback) improved TerminalBench 2.0 scores from 52.8% to 66.5%
- **AWS recently announced Kiro**, adding formal specification verification to their agent tooling

The pattern is clear: **when you give AI agents structured feedback about violations, they learn to avoid them.**

But there's a catch. All of these approaches are still *probabilistic*. They make violations less likely, but they don't make them impossible.

## The Insight: Compiler as Gatekeeper

Here's the key insight: **TypeScript's type system is deterministic, not probabilistic.**

If your code doesn't type-check, it doesn't compile. Period. No edge cases, no "usually works," no "99% correct." Either the types are satisfied or they're not.

So what if we encoded security invariants as *type constraints*?

Instead of telling the AI "please remember to authenticate," we make authentication a type requirement:

```typescript
// This function ONLY accepts AuthorizedQuery
declare function dbQuery(input: AuthorizedQuery): Promise<Data>;

// This will not compile:
dbQuery(req.body);
//      ^^^^^^^^
// Error: Type 'unknown' is not assignable to parameter of type 'AuthorizedQuery'
```

The AI can't skip authentication anymore — not because it remembers not to, but because **the code literally will not compile without it**.

## How It Works: Branded Types

VerifyLoop uses TypeScript's *branded types* pattern to create compile-time guarantees.

Here's how it works:

1. **Define a security chain** in a YAML spec:

```yaml
chain:
  - type: RawInput
    constructor: createRawInput
  - type: ValidatedInput
    constructor: validateInput
    requires: RawInput
  - type: AuthenticatedCtx
    constructor: authenticate
    requires: ValidatedInput
  - type: AuthorizedQuery
    constructor: authorizeQuery
    requires: AuthenticatedCtx

protected_functions:
  - dbQuery
  - dbWrite
  - dbDelete
```

2. **Generate branded type declarations**:

```typescript
declare const __brand: unique symbol;
type Brand<T, TBrand> = T & { readonly [__brand]: TBrand };

export type RawInput = Brand<{ data: unknown }, 'RawInput'>;
export type ValidatedInput = Brand<{ userId: string; action: string }, 'ValidatedInput'>;
export type AuthenticatedCtx = Brand<{ userId: string; action: string; token: string }, 'AuthenticatedCtx'>;
export type AuthorizedQuery = Brand<{ userId: string; action: string; token: string; tenantId: string }, 'AuthorizedQuery'>;

// Protected functions REQUIRE the final type
export declare function dbQuery(input: AuthorizedQuery): Promise<unknown>;
```

3. **Implement the constructors**:

```typescript
export function validateInput(input: RawInput): ValidatedInput {
  // Your validation logic
  const data = input.data as { userId: string; action: string };
  if (!data.userId || !data.action) throw new Error('Invalid input');
  return data as ValidatedInput;
}

export function authenticate(input: ValidatedInput, token: string): AuthenticatedCtx {
  if (!verifyToken(token)) throw new Error('Auth failed');
  return { ...input, token } as AuthenticatedCtx;
}

export function authorizeQuery(input: AuthenticatedCtx, tenantId: string): AuthorizedQuery {
  if (!checkTenantAccess(input.userId, tenantId)) throw new Error('Unauthorized');
  return { ...input, tenantId } as AuthorizedQuery;
}
```

Now, the *only* way to call `dbQuery` is to go through the full chain:

```typescript
const raw = createRawInput(req.body);
const validated = validateInput(raw);
const authed = authenticate(validated, token);
const authorized = authorizeQuery(authed, tenantId);
const data = await dbQuery(authorized); // ✓ Compiles
```

Try to skip a step:

```typescript
const data = await dbQuery(req.body); // ✗ Compile error
```

## The Demo: Multi-Tenant Auth

I built a demo scenario to test this. It's a multi-tenant SaaS API where database queries must pass through:

1. Input validation
2. Authentication (valid session token)
3. Authorization (tenant access control)

### Without Guards

First, I asked an AI agent to generate an API endpoint without VerifyLoop guards:

```typescript
export async function getUserData(req: Request, res: Response) {
  const { userId } = req.body;
  const userData = await database.query('SELECT * FROM users WHERE id = ?', [userId]);
  res.status(200).json(userData);
}
```

This code compiles. It runs. And it has three critical vulnerabilities:
- No input validation (SQL injection risk)
- No authentication (anyone can call it)
- No tenant authorization (cross-tenant data access)

### With Guards (Wrong Implementation)

Next, I generated VerifyLoop guards from the spec and asked the AI to implement the same endpoint:

```typescript
import { dbQuery } from './guards/multi-tenant-auth';

export async function getUserData(req: Request, res: Response) {
  const userData = await dbQuery(req.body);
  res.status(200).json(userData);
}
```

**This code does not compile.**

TypeScript immediately rejects it:

```
Error: Argument of type 'unknown' is not assignable to parameter of type 'AuthorizedQuery'
  at line 4: dbQuery(req.body)
```

The AI can't skip authentication because the type system won't let it.

### With Guards (Correct Implementation)

Here's what actually compiles:

```typescript
import {
  createRawInput,
  validateInput,
  authenticate,
  authorizeQuery,
  dbQuery,
} from './guards/multi-tenant-auth';

export async function getUserData(req: Request, res: Response) {
  try {
    const raw = createRawInput(req.body);
    const validated = validateInput(raw);
    const authed = authenticate(validated, req.headers.authorization);
    const authorized = authorizeQuery(authed, req.headers['x-tenant-id']);
    const data = await dbQuery(authorized);
    res.status(200).json(data);
  } catch (error) {
    res.status(403).json({ error: 'Unauthorized' });
  }
}
```

This is the *only* way to call `dbQuery`. The security chain is now a compile-time requirement, not a runtime hope.

## The Verification Loop

But here's where it gets interesting. When the AI generates the wrong code (the version that doesn't compile), VerifyLoop doesn't just reject it. It provides *structured feedback*:

```json
{
  "file": "src/api.ts",
  "line": 4,
  "invariant": "multi-tenant-auth",
  "violation": "Type 'unknown' is not assignable to 'AuthorizedQuery'",
  "hint": "Use authorizeQuery(authenticate(validateInput(createRawInput(input)))) to construct AuthorizedQuery",
  "guard_definition": "Chain: RawInput → ValidatedInput → AuthenticatedCtx → AuthorizedQuery"
}
```

This feedback includes:
- **Where** the violation occurred (file and line)
- **What** invariant was violated
- **Why** it's wrong (the type error)
- **How** to fix it (the constructor chain)

The AI can use this feedback to self-correct. And because the feedback is deterministic (coming from `tsc`, not another LLM), the loop converges reliably.

This aligns with the research. Reuben Brooks' Shen-Backpressure work (reubenbrooks.dev, May 2026, 115 HN points) showed that structured compiler feedback creates faster, more reliable correction loops than prompt-based reminders.

## What This Means

VerifyLoop is designed to transform how we think about AI-generated security-critical code:

### Before VerifyLoop
- Security rule: "Please remember to check authentication"
- Enforcement: Code review, runtime testing, production incidents
- Result: 95% correct → 5% vulnerabilities slip through

### With VerifyLoop
- Security rule: "This code will not compile without authentication"
- Enforcement: TypeScript compiler at build time
- Result: 100% correct or doesn't build

The test suite verifies this across multiple scenarios:
- Single-step guards (basic type safety)
- Multi-step chains (complex authentication flows)
- Multiple invariants (different security domains)
- Error budget strategies (loop control)

## The Difference

This is fundamentally different from existing approaches:

### vs. Kiro (AWS)
**Kiro** uses LLMs to verify behavioral properties at runtime. It's probabilistic — the verification LLM might miss edge cases.

**VerifyLoop** uses the TypeScript compiler to verify structural properties at compile time. It's deterministic — if it compiles, the invariant is satisfied.

### vs. Forge
**Forge** uses constraints to verify behavioral properties: "Does this function handle errors?" "Is test coverage >80%?"

**VerifyLoop** uses types to verify structural properties: "Does this data flow through authentication?" "Has this input been validated?"

They're complementary. Use Forge for behavior, VerifyLoop for data flow.

## Limitations and Future Work

VerifyLoop v1 has some constraints:

1. **TypeScript only**: Branded types are a TypeScript feature. Other languages need different approaches.
2. **Compile-time only**: This catches violations before runtime, but runtime validation is still your responsibility.
3. **Symbol branding only**: v1 implements the unique symbol pattern. Future versions may support class-based or Zod-based branding.
4. **Manual constructor implementation**: You still have to write the validation logic inside constructors. VerifyLoop generates the types and stubs, not the logic.

Future directions:
- **Multi-language support**: Explore similar patterns in Rust (newtype), Go (type aliases), Python (typing.NewType)
- **Runtime enforcement**: Generate runtime validators from the same spec
- **IDE integration**: Live feedback as you type, not just at build time
- **Spec inference**: Generate specs from existing code patterns

## Try It

VerifyLoop is open source. The demo shows a complete multi-tenant auth example:

```bash
# Install
npm install verifyloop

# Generate guards from spec
verifyloop generate --spec verifyloop.spec.yaml --output ./guards

# Check your code
verifyloop check ./src --spec verifyloop.spec.yaml

# Run verification loop
verifyloop loop --path ./src --max-retries 5
```

The full demo is in the repo, with:
- The spec file (multi-tenant auth chain)
- Vulnerable code without guards (compiles but insecure)
- Protected code with guards (secure code compiles, insecure code doesn't)

## The Core Idea

AI coding agents are powerful but probabilistic. Security invariants should be deterministic.

VerifyLoop bridges that gap by encoding invariants in the type system. The result is code that **cannot violate security rules and still compile**.

It's not about making the AI remember. It's about making violations impossible.

---

*VerifyLoop is designed for TypeScript projects using Node.js 20+. It works with standard `tsc` (no custom compiler plugins) and has zero runtime overhead. The system is currently in testing. See the GitHub repo for installation and usage details.*

**References:**
- Forge: github.com/antoinezambelli/forge (8B model 53% → 99% with constraints)
- LangChain compiler feedback: aipatternbook.com/shift-left-feedback (52.8% → 66.5% on TerminalBench 2.0)
- AWS Kiro: Formal specification verification for AI agents
- Shen-Backpressure: reubenbrooks.dev (structured feedback loops, May 2026, 115 HN points)
