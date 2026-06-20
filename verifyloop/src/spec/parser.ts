import { readFileSync } from 'fs';
import { parse as parseYaml } from 'yaml';
import type { VerifyLoopSpec, Invariant, ChainStep, Settings } from './types.js';

export class SpecParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SpecParseError';
  }
}

export function parseSpec(specPath: string): VerifyLoopSpec {
  let content: string;
  try {
    content = readFileSync(specPath, 'utf-8');
  } catch (error) {
    throw new SpecParseError(`Failed to read spec file at ${specPath}: ${error}`);
  }

  let parsed: unknown;
  try {
    parsed = parseYaml(content);
  } catch (error) {
    throw new SpecParseError(`Failed to parse YAML: ${error}`);
  }

  if (!parsed || typeof parsed !== 'object') {
    throw new SpecParseError('Spec must be a YAML object');
  }

  const spec = parsed as Record<string, unknown>;

  // Validate version
  if (!spec.version || typeof spec.version !== 'string') {
    throw new SpecParseError('Spec must have a "version" field of type string');
  }

  // Validate invariants
  if (!spec.invariants || !Array.isArray(spec.invariants)) {
    throw new SpecParseError('Spec must have an "invariants" field of type array');
  }

  const invariants = spec.invariants.map((inv, idx) => {
    if (!inv || typeof inv !== 'object') {
      throw new SpecParseError(`Invariant at index ${idx} must be an object`);
    }
    return validateInvariant(inv as Record<string, unknown>, idx);
  });

  return {
    version: spec.version,
    invariants,
  };
}

function validateInvariant(inv: Record<string, unknown>, idx: number): Invariant {
  // Validate name
  if (!inv.name || typeof inv.name !== 'string') {
    throw new SpecParseError(`Invariant at index ${idx} must have a "name" field of type string`);
  }

  // Validate description
  if (!inv.description || typeof inv.description !== 'string') {
    throw new SpecParseError(`Invariant "${inv.name}" must have a "description" field of type string`);
  }

  // Validate chain
  if (!inv.chain || !Array.isArray(inv.chain)) {
    throw new SpecParseError(`Invariant "${inv.name}" must have a "chain" field of type array`);
  }

  const chain = inv.chain.map((step, stepIdx) => {
    if (!step || typeof step !== 'object') {
      throw new SpecParseError(`Chain step at index ${stepIdx} in invariant "${inv.name}" must be an object`);
    }
    return validateChainStep(step as Record<string, unknown>, stepIdx, inv.name as string);
  });

  // Validate protected_functions
  if (!inv.protected_functions || !Array.isArray(inv.protected_functions)) {
    throw new SpecParseError(`Invariant "${inv.name}" must have a "protected_functions" field of type array`);
  }

  const protectedFunctions = inv.protected_functions;
  if (!protectedFunctions.every(fn => typeof fn === 'string')) {
    throw new SpecParseError(`Invariant "${inv.name}" protected_functions must all be strings`);
  }

  // Validate settings (optional)
  let settings: Settings | undefined;
  if (inv.settings) {
    if (typeof inv.settings !== 'object') {
      throw new SpecParseError(`Invariant "${inv.name}" settings must be an object`);
    }
    settings = validateSettings(inv.settings as Record<string, unknown>, inv.name as string);
  }

  return {
    name: inv.name as string,
    description: inv.description as string,
    chain,
    protected_functions: protectedFunctions as string[],
    settings,
  };
}

function validateChainStep(step: Record<string, unknown>, idx: number, invariantName: string): ChainStep {
  // Validate type
  if (!step.type || typeof step.type !== 'string') {
    throw new SpecParseError(`Chain step at index ${idx} in invariant "${invariantName}" must have a "type" field of type string`);
  }

  // Validate constructor
  if (!step.constructor || typeof step.constructor !== 'string') {
    throw new SpecParseError(`Chain step at index ${idx} in invariant "${invariantName}" must have a "constructor" field of type string`);
  }

  // Validate description
  if (!step.description || typeof step.description !== 'string') {
    throw new SpecParseError(`Chain step at index ${idx} in invariant "${invariantName}" must have a "description" field of type string`);
  }

  // Validate fields (optional)
  let fields: Record<string, string> | undefined;
  if (step.fields) {
    if (typeof step.fields !== 'object' || Array.isArray(step.fields)) {
      throw new SpecParseError(`Chain step at index ${idx} in invariant "${invariantName}" fields must be an object`);
    }
    fields = step.fields as Record<string, string>;
  }

  // Validate requires (optional)
  let requires: string | undefined;
  if (step.requires) {
    if (typeof step.requires !== 'string') {
      throw new SpecParseError(`Chain step at index ${idx} in invariant "${invariantName}" requires must be a string`);
    }
    requires = step.requires;
  }

  return {
    type: step.type as string,
    fields,
    requires,
    constructor: step.constructor as string,
    description: step.description as string,
  };
}

function validateSettings(settings: Record<string, unknown>, invariantName: string): Settings {
  const result: Settings = {};

  if (settings.max_retries !== undefined) {
    if (typeof settings.max_retries !== 'number' || settings.max_retries < 0) {
      throw new SpecParseError(`Invariant "${invariantName}" settings.max_retries must be a non-negative number`);
    }
    result.max_retries = settings.max_retries;
  }

  if (settings.error_budget !== undefined) {
    if (typeof settings.error_budget !== 'string' ||
        !['increasing', 'decreasing', 'none'].includes(settings.error_budget)) {
      throw new SpecParseError(`Invariant "${invariantName}" settings.error_budget must be "increasing", "decreasing", or "none"`);
    }
    result.error_budget = settings.error_budget as 'increasing' | 'decreasing' | 'none';
  }

  if (settings.brand_style !== undefined) {
    if (typeof settings.brand_style !== 'string' ||
        !['symbol', 'class', 'zod'].includes(settings.brand_style)) {
      throw new SpecParseError(`Invariant "${invariantName}" settings.brand_style must be "symbol", "class", or "zod"`);
    }
    result.brand_style = settings.brand_style as 'symbol' | 'class' | 'zod';
  }

  return result;
}
