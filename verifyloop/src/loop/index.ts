import { verify, type VerificationGateOptions } from '../gate/index.js';
import type { Invariant, ErrorBudgetStrategy } from '../spec/types.js';
import type { LoopResult, RetryAttempt } from './types.js';

export interface LoopOptions {
  targetPath: string;
  invariants: Invariant[];
  maxRetries?: number;
  errorBudget?: ErrorBudgetStrategy;
  tsconfigPath?: string;
  onRetry?: (attempt: RetryAttempt) => void | Promise<void>;
}

export async function runVerificationLoop(options: LoopOptions): Promise<LoopResult> {
  const {
    targetPath,
    invariants,
    maxRetries = 5,
    errorBudget = 'none',
    tsconfigPath,
    onRetry,
  } = options;

  const attempts: RetryAttempt[] = [];
  let currentAttempt = 0;

  while (currentAttempt <= maxRetries) {
    const verificationOptions: VerificationGateOptions = {
      targetPath,
      invariants,
      tsconfigPath,
    };

    const result = verify(verificationOptions);

    // Count total TypeScript errors (both guard-related and warnings)
    const totalErrorCount = result.errors.length + result.warnings.length;

    const attempt: RetryAttempt = {
      attempt: currentAttempt,
      timestamp: new Date(),
      errorCount: totalErrorCount,
      errors: [...result.errors, ...result.warnings],
    };

    attempts.push(attempt);

    if (result.success && result.warnings.length === 0) {
      // Success - all TypeScript errors resolved (both guard and non-guard)
      return {
        status: 'PASS',
        attempts,
        finalErrorCount: 0,
        message: `Verification passed after ${currentAttempt} attempt(s)`,
      };
    }

    // Check if we've exhausted retries
    if (currentAttempt >= maxRetries) {
      return {
        status: 'FAIL',
        attempts,
        finalErrorCount: totalErrorCount,
        message: `Verification failed after ${maxRetries} retry attempts. ${totalErrorCount} error(s) remaining.`,
      };
    }

    // Check error budget
    if (errorBudget !== 'none' && attempts.length > 1) {
      const previousErrorCount = attempts[attempts.length - 2].errorCount;
      const currentErrorCount = attempt.errorCount;

      const shouldAbort = checkErrorBudget(
        errorBudget,
        previousErrorCount,
        currentErrorCount
      );

      if (shouldAbort) {
        return {
          status: 'ABORTED',
          attempts,
          finalErrorCount: currentErrorCount,
          message: `Verification aborted: error budget violated. Error count ${previousErrorCount} → ${currentErrorCount}`,
        };
      }
    }

    // Notify retry callback
    if (onRetry) {
      await onRetry(attempt);
    }

    currentAttempt++;
  }

  // Should never reach here, but TypeScript doesn't know that
  return {
    status: 'FAIL',
    attempts,
    finalErrorCount: attempts[attempts.length - 1]?.errorCount || 0,
    message: 'Verification loop completed without resolution',
  };
}

function checkErrorBudget(
  strategy: ErrorBudgetStrategy,
  previousCount: number,
  currentCount: number
): boolean {
  switch (strategy) {
    case 'increasing':
      // Abort if errors increased
      return currentCount > previousCount;
    case 'decreasing':
      // Abort if errors didn't decrease
      return currentCount >= previousCount;
    case 'none':
      return false;
    default:
      return false;
  }
}

export { LoopResult, LoopStatus, RetryAttempt } from './types.js';
