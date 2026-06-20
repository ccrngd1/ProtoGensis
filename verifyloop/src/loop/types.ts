import type { VerificationError } from '../gate/types.js';

export type LoopStatus = 'PASS' | 'FAIL' | 'ABORTED';

export interface RetryAttempt {
  attempt: number;
  timestamp: Date;
  errorCount: number;
  errors: VerificationError[];
}

export interface LoopResult {
  status: LoopStatus;
  attempts: RetryAttempt[];
  finalErrorCount: number;
  message: string;
}
