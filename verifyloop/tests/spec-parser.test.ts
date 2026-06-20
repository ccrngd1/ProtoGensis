import { describe, it, expect } from 'vitest';
import { writeFileSync, mkdirSync, rmSync } from 'fs';
import { join } from 'path';
import { parseSpec, SpecParseError } from '../src/spec/parser.js';

const TEST_DIR = '/tmp/verifyloop-test';

describe('Spec Parser', () => {
  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it('should parse valid spec', () => {
    const specPath = join(TEST_DIR, 'valid.yaml');
    const spec = `
version: "1.0"
invariants:
  - name: test-invariant
    description: "Test description"
    chain:
      - type: TypeA
        constructor: createA
        description: "Create A"
      - type: TypeB
        constructor: createB
        requires: TypeA
        description: "Create B"
        fields:
          foo: string
    protected_functions:
      - someFunc
    settings:
      max_retries: 3
      error_budget: increasing
      brand_style: symbol
`;
    writeFileSync(specPath, spec);

    const result = parseSpec(specPath);

    expect(result.version).toBe('1.0');
    expect(result.invariants).toHaveLength(1);
    expect(result.invariants[0].name).toBe('test-invariant');
    expect(result.invariants[0].chain).toHaveLength(2);
    expect(result.invariants[0].chain[0].type).toBe('TypeA');
    expect(result.invariants[0].chain[1].requires).toBe('TypeA');
    expect(result.invariants[0].settings?.max_retries).toBe(3);
    expect(result.invariants[0].settings?.error_budget).toBe('increasing');
  });

  it('should reject spec without version', () => {
    const specPath = join(TEST_DIR, 'no-version.yaml');
    const spec = `
invariants:
  - name: test
    description: "Test"
    chain: []
    protected_functions: []
`;
    writeFileSync(specPath, spec);

    expect(() => parseSpec(specPath)).toThrow(SpecParseError);
    expect(() => parseSpec(specPath)).toThrow('version');
  });

  it('should reject spec without invariants', () => {
    const specPath = join(TEST_DIR, 'no-invariants.yaml');
    const spec = `
version: "1.0"
`;
    writeFileSync(specPath, spec);

    expect(() => parseSpec(specPath)).toThrow(SpecParseError);
    expect(() => parseSpec(specPath)).toThrow('invariants');
  });

  it('should reject invariant without name', () => {
    const specPath = join(TEST_DIR, 'no-name.yaml');
    const spec = `
version: "1.0"
invariants:
  - description: "Test"
    chain: []
    protected_functions: []
`;
    writeFileSync(specPath, spec);

    expect(() => parseSpec(specPath)).toThrow(SpecParseError);
    expect(() => parseSpec(specPath)).toThrow('name');
  });

  it('should reject chain step without required fields', () => {
    const specPath = join(TEST_DIR, 'invalid-chain.yaml');
    const spec = `
version: "1.0"
invariants:
  - name: test
    description: "Test"
    chain:
      - type: TypeA
    protected_functions: []
`;
    writeFileSync(specPath, spec);

    expect(() => parseSpec(specPath)).toThrow(SpecParseError);
  });

  it('should handle optional fields correctly', () => {
    const specPath = join(TEST_DIR, 'optional-fields.yaml');
    const spec = `
version: "1.0"
invariants:
  - name: test
    description: "Test"
    chain:
      - type: TypeA
        constructor: createA
        description: "Create A"
    protected_functions:
      - func1
`;
    writeFileSync(specPath, spec);

    const result = parseSpec(specPath);

    expect(result.invariants[0].settings).toBeUndefined();
    expect(result.invariants[0].chain[0].fields).toBeUndefined();
    expect(result.invariants[0].chain[0].requires).toBeUndefined();
  });

  it('should reject invalid error_budget value', () => {
    const specPath = join(TEST_DIR, 'invalid-budget.yaml');
    const spec = `
version: "1.0"
invariants:
  - name: test
    description: "Test"
    chain:
      - type: TypeA
        constructor: createA
        description: "Create A"
    protected_functions: []
    settings:
      error_budget: invalid
`;
    writeFileSync(specPath, spec);

    expect(() => parseSpec(specPath)).toThrow(SpecParseError);
    expect(() => parseSpec(specPath)).toThrow('error_budget');
  });

  it('should reject invalid brand_style value', () => {
    const specPath = join(TEST_DIR, 'invalid-brand.yaml');
    const spec = `
version: "1.0"
invariants:
  - name: test
    description: "Test"
    chain:
      - type: TypeA
        constructor: createA
        description: "Create A"
    protected_functions: []
    settings:
      brand_style: invalid
`;
    writeFileSync(specPath, spec);

    expect(() => parseSpec(specPath)).toThrow(SpecParseError);
    expect(() => parseSpec(specPath)).toThrow('brand_style');
  });

  it('should reject non-existent file', () => {
    expect(() => parseSpec('/nonexistent/file.yaml')).toThrow(SpecParseError);
  });

  it('should reject invalid YAML', () => {
    const specPath = join(TEST_DIR, 'invalid.yaml');
    writeFileSync(specPath, 'invalid: yaml: content: [[[');

    expect(() => parseSpec(specPath)).toThrow(SpecParseError);
  });
});
