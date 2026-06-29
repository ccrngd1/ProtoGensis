import { describe, it, expect } from 'vitest';
import { writeFileSync, mkdirSync, rmSync } from 'fs';
import { join } from 'path';
import { verify } from '../src/gate/index.js';
import type { Invariant } from '../src/spec/types.js';

const TEST_DIR = '/tmp/verifyloop-gate-test';

describe('Verification Gate', () => {
  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it('should pass on valid TypeScript code', () => {
    const filePath = join(TEST_DIR, 'valid.ts');
    writeFileSync(filePath, `
      const x: number = 42;
      const y: string = "hello";
    `);

    const invariants: Invariant[] = [];

    const result = verify({
      targetPath: filePath,
      invariants,
    });

    expect(result.success).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('should detect TypeScript errors', () => {
    const filePath = join(TEST_DIR, 'invalid.ts');
    writeFileSync(filePath, `
      const x: number = "string";
    `);

    const invariants: Invariant[] = [];

    const result = verify({
      targetPath: filePath,
      invariants,
    });

    expect(result.success).toBe(true); // No guard errors
    expect(result.warnings.length).toBeGreaterThan(0); // But has warnings
  });

  it('should identify guard-related errors', () => {
    // Create a guard file
    const guardPath = join(TEST_DIR, 'guard.d.ts');
    writeFileSync(guardPath, `
      declare const __brand: unique symbol;
      type Brand<T, TBrand> = T & { readonly [__brand]: TBrand };
      export type AuthorizedQuery = Brand<{ userId: string }, 'AuthorizedQuery'>;
      export declare function dbQuery(input: AuthorizedQuery): Promise<unknown>;
    `);

    // Create code that violates the guard
    const codePath = join(TEST_DIR, 'code.ts');
    writeFileSync(codePath, `
      import { dbQuery } from './guard';
      const data = { userId: "123" };
      dbQuery(data);
    `);

    const invariants: Invariant[] = [
      {
        name: 'auth-guard',
        description: 'Auth guard',
        chain: [
          {
            type: 'AuthorizedQuery',
            constructor: 'authorize',
            description: 'Authorize',
          },
        ],
        protected_functions: ['dbQuery'],
      },
    ];

    const result = verify({
      targetPath: codePath,
      invariants,
    });

    expect(result.success).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);

    const guardError = result.errors.find(e => e.is_guard_related);
    expect(guardError).toBeDefined();
    expect(guardError?.invariant).toBe('auth-guard');
  });

  it('should generate hints for guard violations', () => {
    const guardPath = join(TEST_DIR, 'guard.d.ts');
    writeFileSync(guardPath, `
      declare const __brand: unique symbol;
      type Brand<T, TBrand> = T & { readonly [__brand]: TBrand };
      export type Step1 = Brand<{}, 'Step1'>;
      export type Step2 = Brand<{}, 'Step2'>;
      export declare function step1(): Step1;
      export declare function step2(input: Step1): Step2;
      export declare function protectedFunc(input: Step2): void;
    `);

    const codePath = join(TEST_DIR, 'code.ts');
    writeFileSync(codePath, `
      import { protectedFunc } from './guard';
      // Trying to call protected function with wrong type
      protectedFunc({});  // This should cause type error
    `);

    const invariants: Invariant[] = [
      {
        name: 'two-step',
        description: 'Two step chain',
        chain: [
          {
            type: 'Step1',
            constructor: 'step1',
            description: 'Step 1',
          },
          {
            type: 'Step2',
            constructor: 'step2',
            requires: 'Step1',
            description: 'Step 2',
          },
        ],
        protected_functions: ['protectedFunc'],
      },
    ];

    const result = verify({
      targetPath: codePath,
      invariants,
    });

    const guardError = result.errors.find(e => e.is_guard_related);
    expect(guardError?.hint).toBeDefined();
    expect(guardError?.hint).toContain('step1');
    expect(guardError?.hint).toContain('step2');
  });

  it('should separate guard errors from warnings', () => {
    const guardPath = join(TEST_DIR, 'guard.d.ts');
    writeFileSync(guardPath, `
      declare const __brand: unique symbol;
      type Brand<T, TBrand> = T & { readonly [__brand]: TBrand };
      export type Guarded = Brand<{}, 'Guarded'>;
      export declare function guardedFunc(input: Guarded): void;
    `);

    const codePath = join(TEST_DIR, 'code.ts');
    writeFileSync(codePath, `
      import { guardedFunc } from './guard';

      // Guard violation
      guardedFunc({});

      // Regular type error (not guard-related)
      const x: number = "string";
    `);

    const invariants: Invariant[] = [
      {
        name: 'guard',
        description: 'Guard',
        chain: [
          {
            type: 'Guarded',
            constructor: 'guard',
            description: 'Guard',
          },
        ],
        protected_functions: ['guardedFunc'],
      },
    ];

    const result = verify({
      targetPath: codePath,
      invariants,
    });

    expect(result.success).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.warnings.length).toBeGreaterThan(0);

    // Guard errors should block
    expect(result.errors.every(e => e.is_guard_related)).toBe(true);
    // Warnings should be non-guard errors
    expect(result.warnings.every(e => !e.is_guard_related)).toBe(true);
  });
});
