/**
 * VULNERABLE: Without Guards
 *
 * This code appears to work but has a critical security flaw:
 * it performs direct database queries without proper authentication/authorization.
 *
 * An AI agent could easily generate this code when asked to "add an API endpoint
 * to fetch user data" without being explicitly reminded about security.
 */

interface Request {
  body: unknown;
  headers: Record<string, string>;
}

interface Response {
  status(code: number): Response;
  json(data: unknown): void;
}

// Simulated database
const database = {
  async query(sql: string, params: unknown[]): Promise<unknown[]> {
    console.log('Executing query:', sql, params);
    return [];
  },
};

/**
 * VULNERABILITY: This endpoint directly queries the database
 * without validating input, checking authentication, or verifying tenant authorization.
 */
export async function getUserData(req: Request, res: Response) {
  // No input validation
  const { userId } = req.body as { userId: string };

  // No authentication check
  // No tenant authorization

  // DIRECT DATABASE ACCESS - SECURITY VIOLATION
  const userData = await database.query(
    'SELECT * FROM users WHERE id = ?',
    [userId]
  );

  res.status(200).json(userData);
}

/**
 * VULNERABILITY: Direct database write without any security checks
 */
export async function updateUserData(req: Request, res: Response) {
  const { userId, newData } = req.body as { userId: string; newData: unknown };

  // DIRECT DATABASE ACCESS - SECURITY VIOLATION
  await database.query(
    'UPDATE users SET data = ? WHERE id = ?',
    [newData, userId]
  );

  res.status(200).json({ success: true });
}

/**
 * In a real scenario, this code would compile and run fine,
 * but would expose critical security vulnerabilities:
 *
 * 1. Cross-tenant data access (tenant A can access tenant B's data)
 * 2. Unauthenticated access (no token validation)
 * 3. SQL injection (no input validation)
 * 4. No audit trail
 */
