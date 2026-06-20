/**
 * WITH GUARDS (WRONG IMPLEMENTATION)
 *
 * This is what an AI agent might generate on first attempt.
 * It will NOT compile because it violates the guard chain.
 */

import { dbQuery, type AuthorizedQuery } from '@guards/multi-tenant-auth';

interface Request {
  body: unknown;
  headers: Record<string, string>;
}

interface Response {
  status(code: number): Response;
  json(data: unknown): void;
}

/**
 * TypeScript will reject this code at compile time
 * because dbQuery requires AuthorizedQuery, but we're passing unknown
 */
export async function getUserData(req: Request, res: Response) {
  const { userId } = req.body as { userId: string };

  // TYPE ERROR: Argument of type 'unknown' is not assignable to parameter of type 'AuthorizedQuery'
  // This will NOT compile!
  const userData = await dbQuery(req.body);

  res.status(200).json(userData);
}
