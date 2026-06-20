/**
 * WITH GUARDS (CORRECT IMPLEMENTATION)
 *
 * This code properly chains through all validation steps.
 * TypeScript enforces the security invariant at compile time.
 */

import {
  createRawInput,
  validateInput,
  authenticate,
  authorizeQuery,
  dbQuery,
  type RawInput,
  type ValidatedInput,
  type AuthenticatedCtx,
  type AuthorizedQuery,
} from '@guards/multi-tenant-auth';

interface Request {
  body: unknown;
  headers: Record<string, string>;
}

interface Response {
  status(code: number): Response;
  json(data: unknown): void;
}

/**
 * SECURE: This endpoint properly chains through all security steps
 * TypeScript ensures we cannot skip any step in the chain
 */
export async function getUserData(req: Request, res: Response) {
  try {
    // Step 1: Create raw input
    const rawInput: RawInput = createRawInput(req.body);

    // Step 2: Validate input (schema validation, sanitization)
    const validatedInput: ValidatedInput = validateInput(rawInput);

    // Step 3: Authenticate (verify session token)
    const token = req.headers['authorization']?.replace('Bearer ', '') || '';
    const authenticatedCtx: AuthenticatedCtx = authenticate(validatedInput, token);

    // Step 4: Authorize (check tenant access)
    const tenantId = req.headers['x-tenant-id'] || '';
    const authorizedQuery: AuthorizedQuery = authorizeQuery(authenticatedCtx, tenantId);

    // Step 5: Execute query - TypeScript enforces that we have AuthorizedQuery
    const userData = await dbQuery(authorizedQuery);

    res.status(200).json(userData);
  } catch (error) {
    res.status(403).json({ error: 'Unauthorized' });
  }
}

/**
 * It is literally impossible to write code that skips authentication
 * and still compiles. The type system makes security violations a compile error.
 *
 * Try to write:
 *   await dbQuery(req.body)
 *
 * TypeScript will reject it:
 *   Type 'unknown' is not assignable to type 'AuthorizedQuery'
 */
