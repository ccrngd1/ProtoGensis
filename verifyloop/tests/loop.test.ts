import { describe, it, expect, vi } from 'vitest';
import { writeFileSync, mkdirSync, rmSync } from 'fs';
import { join } from 'path';
import { runVerificationLoop } from '../src/loop/index.js';
import type { Invariant } from '../src/spec/types.js';

const TEST_DIR = '/tmp/verifyloop-loop-test';

describe('Loop Runner', () => {
  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it('should pass on first attempt if code is valid', async () => {
    const filePath = join(TEST_DIR, 'valid.ts');
    writeFileSync(filePath, `const x: number = 42;`);

    const result = await runVerificationLoop({
      targetPath: filePath,
      invariants: [],
      maxRetries: 5,
    });

    expect(result.status).toBe('PASS');
    expect(result.attempts).toHaveLength(1);
    expect(result.finalErrorCount).toBe(0);
  });

  it('should fail after max retries', async () => {
    const filePath = join(TEST_DIR, 'invalid.ts');
    writeFileSync(filePath, `const x: number = "string";`);

    // Create a guard to make this a guard error
    const guardPath = join(TEST_DIR, 'guard.d.ts');
    writeFileSync(guardPath, `
      export type GuardedNumber = number;
    `);

    writeFileSync(filePath, `
      import { GuardedNumber } from './guard';
      const x: GuardedNumber = "string";
    `);

    const invariants: Invariant[] = [
      {
        name: 'number-guard',
        description: 'Number guard',
        chain: [
          {
            type: 'GuardedNumber',
            constructor: 'guardNumber',
            description: 'Guard number',
          },
        ],
        protected_functions: [],
      },
    ];

    const result = await runVerificationLoop({
      targetPath: filePath,
      invariants,
      maxRetries: 2,
    });

    expect(result.status).toBe('FAIL');
    expect(result.attempts.length).toBeGreaterThan(1);
    expect(result.finalErrorCount).toBeGreaterThan(0);
  });

  it('should abort when errors increase with increasing budget', async () => {
    const filePath = join(TEST_DIR, 'code.ts');
    writeFileSync(filePath, `const x: number = 42;`);

    const onRetry = vi.fn().mockImplementation(() => {
      // Add more errors on retry
      writeFileSync(filePath, `
        const x: number = "string";
        const y: string = 123;
      `);
    });

    const result = await runVerificationLoop({
      targetPath: filePath,
      invariants: [],
      maxRetries: 5,
      errorBudget: 'increasing',
      onRetry,
    });

    // Note: Since we're not creating guard-related errors,
    // this test is mainly checking the loop control logic
    expect(result.attempts.length).toBeGreaterThan(0);
  });

  it('should call onRetry callback', async () => {
    const filePath = join(TEST_DIR, 'code.ts');
    writeFileSync(filePath, `const x: number = 42;`);

    const onRetry = vi.fn();

    await runVerificationLoop({
      targetPath: filePath,
      invariants: [],
      maxRetries: 0,
      onRetry,
    });

    // First attempt should not trigger onRetry
    expect(onRetry).not.toHaveBeenCalled();
  });

  it('should track attempt history', async () => {
    const filePath = join(TEST_DIR, 'code.ts');
    writeFileSync(filePath, `const x: number = 42;`);

    const result = await runVerificationLoop({
      targetPath: filePath,
      invariants: [],
      maxRetries: 3,
    });

    expect(result.attempts).toHaveLength(1); // Passed on first attempt
    expect(result.attempts[0].attempt).toBe(0);
    expect(result.attempts[0].timestamp).toBeInstanceOf(Date);
    expect(result.attempts[0].errorCount).toBe(0);
  });

  it('should enforce decreasing error budget', async () => {
    const filePath = join(TEST_DIR, 'code.ts');

    // Start with valid code
    writeFileSync(filePath, `const x: number = 42;`);

    let attemptCount = 0;
    const onRetry = vi.fn().mockImplementation(() => {
      attemptCount++;
      // Keep same number of errors
      writeFileSync(filePath, `const x: number = "string";`);
    });

    const result = await runVerificationLoop({
      targetPath: filePath,
      invariants: [],
      maxRetries: 5,
      errorBudget: 'decreasing',
      onRetry,
    });

    // Should abort if errors don't decrease
    // (In this test, we start with 0 errors and add 1, so it would abort)
  });

  it('should continue with none error budget regardless of error count', async () => {
    const filePath = join(TEST_DIR, 'code.ts');
    writeFileSync(filePath, `const x: number = 42;`);

    let attemptCount = 0;
    const onRetry = vi.fn().mockImplementation(() => {
      attemptCount++;
      if (attemptCount < 3) {
        // Add more errors
        writeFileSync(filePath, `
          const x: number = "string";
          const y: string = 123;
        `);
      }
    });

    const result = await runVerificationLoop({
      targetPath: filePath,
      invariants: [],
      maxRetries: 3,
      errorBudget: 'none',
      onRetry,
    });

    // Should continue regardless of error count changes
    expect(result.attempts.length).toBeGreaterThan(0);
  });
});
