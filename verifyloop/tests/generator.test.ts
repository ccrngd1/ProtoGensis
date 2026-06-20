import { describe, it, expect } from 'vitest';
import { readFileSync, mkdirSync, rmSync, existsSync } from 'fs';
import { join } from 'path';
import { generateGuards } from '../src/generator/index.js';
import type { Invariant } from '../src/spec/types.js';

const TEST_DIR = '/tmp/verifyloop-generator-test';

describe('Guard Generator', () => {
  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it('should generate guard files', () => {
    const invariants: Invariant[] = [
      {
        name: 'test-guard',
        description: 'Test guard',
        chain: [
          {
            type: 'TypeA',
            constructor: 'createA',
            description: 'Create A',
          },
          {
            type: 'TypeB',
            constructor: 'createB',
            requires: 'TypeA',
            description: 'Create B',
            fields: {
              foo: 'string',
              bar: 'number',
            },
          },
        ],
        protected_functions: ['testFunc'],
      },
    ];

    generateGuards(invariants, { outputDir: TEST_DIR });

    // Check that files were created
    expect(existsSync(join(TEST_DIR, 'test-guard.d.ts'))).toBe(true);
    expect(existsSync(join(TEST_DIR, 'test-guard.ts'))).toBe(true);
    expect(existsSync(join(TEST_DIR, 'index.ts'))).toBe(true);
  });

  it('should generate correct type declarations', () => {
    const invariants: Invariant[] = [
      {
        name: 'auth-chain',
        description: 'Authentication chain',
        chain: [
          {
            type: 'RawInput',
            constructor: 'createRaw',
            description: 'Raw input',
          },
          {
            type: 'ValidatedInput',
            constructor: 'validate',
            requires: 'RawInput',
            description: 'Validated input',
            fields: {
              userId: 'string',
            },
          },
        ],
        protected_functions: ['dbQuery'],
      },
    ];

    generateGuards(invariants, { outputDir: TEST_DIR });

    const dtsContent = readFileSync(join(TEST_DIR, 'auth-chain.d.ts'), 'utf-8');

    // Check for brand type definition
    expect(dtsContent).toContain('declare const __brand: unique symbol');
    expect(dtsContent).toContain('type Brand<T, TBrand');

    // Check for type declarations
    expect(dtsContent).toContain('export type RawInput');
    expect(dtsContent).toContain('export type ValidatedInput');

    // Check for constructor signatures
    expect(dtsContent).toContain('export declare function createRaw');
    expect(dtsContent).toContain('export declare function validate');

    // Check for protected function
    expect(dtsContent).toContain('export declare function dbQuery');
    expect(dtsContent).toContain('input: ValidatedInput');
  });

  it('should generate correct implementation stubs', () => {
    const invariants: Invariant[] = [
      {
        name: 'simple',
        description: 'Simple guard',
        chain: [
          {
            type: 'TypeA',
            constructor: 'createA',
            description: 'Create A',
          },
        ],
        protected_functions: ['protectedFunc'],
      },
    ];

    generateGuards(invariants, { outputDir: TEST_DIR });

    const tsContent = readFileSync(join(TEST_DIR, 'simple.ts'), 'utf-8');

    // Check for imports
    expect(tsContent).toContain("import type");
    expect(tsContent).toContain("TypeA");

    // Check for constructor implementation
    expect(tsContent).toContain('export function createA');
    expect(tsContent).toContain('TODO: Implement createA');

    // Check for protected function implementation
    expect(tsContent).toContain('export async function protectedFunc');
  });

  it('should generate barrel export', () => {
    const invariants: Invariant[] = [
      {
        name: 'guard1',
        description: 'Guard 1',
        chain: [
          {
            type: 'Type1',
            constructor: 'create1',
            description: 'Create 1',
          },
        ],
        protected_functions: [],
      },
      {
        name: 'guard2',
        description: 'Guard 2',
        chain: [
          {
            type: 'Type2',
            constructor: 'create2',
            description: 'Create 2',
          },
        ],
        protected_functions: [],
      },
    ];

    generateGuards(invariants, { outputDir: TEST_DIR });

    const indexContent = readFileSync(join(TEST_DIR, 'index.ts'), 'utf-8');

    expect(indexContent).toContain("export * from './guard1.js'");
    expect(indexContent).toContain("export * from './guard2.js'");
  });

  it('should handle chain with requires correctly', () => {
    const invariants: Invariant[] = [
      {
        name: 'chain',
        description: 'Chain test',
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
        protected_functions: [],
      },
    ];

    generateGuards(invariants, { outputDir: TEST_DIR });

    const dtsContent = readFileSync(join(TEST_DIR, 'chain.d.ts'), 'utf-8');

    // step2 should have Step1 as parameter
    expect(dtsContent).toContain('export declare function step2(input: Step1): Step2');
  });

  it('should handle fields correctly', () => {
    const invariants: Invariant[] = [
      {
        name: 'fields',
        description: 'Fields test',
        chain: [
          {
            type: 'WithFields',
            constructor: 'createWithFields',
            description: 'With fields',
            fields: {
              name: 'string',
              age: 'number',
              active: 'boolean',
            },
          },
        ],
        protected_functions: [],
      },
    ];

    generateGuards(invariants, { outputDir: TEST_DIR });

    const dtsContent = readFileSync(join(TEST_DIR, 'fields.d.ts'), 'utf-8');

    expect(dtsContent).toContain('name: string');
    expect(dtsContent).toContain('age: number');
    expect(dtsContent).toContain('active: boolean');
  });

  it('should handle multiple protected functions', () => {
    const invariants: Invariant[] = [
      {
        name: 'multi',
        description: 'Multiple functions',
        chain: [
          {
            type: 'Authorized',
            constructor: 'authorize',
            description: 'Authorize',
          },
        ],
        protected_functions: ['funcA', 'funcB', 'funcC'],
      },
    ];

    generateGuards(invariants, { outputDir: TEST_DIR });

    const dtsContent = readFileSync(join(TEST_DIR, 'multi.d.ts'), 'utf-8');

    expect(dtsContent).toContain('export declare function funcA');
    expect(dtsContent).toContain('export declare function funcB');
    expect(dtsContent).toContain('export declare function funcC');
  });
});
