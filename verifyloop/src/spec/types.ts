export type BrandStyle = 'symbol' | 'class' | 'zod';

export type ErrorBudgetStrategy = 'increasing' | 'decreasing' | 'none';

export interface ChainStep {
  type: string;
  fields?: Record<string, string>;
  requires?: string;
  constructor: string;
  description: string;
}

export interface Settings {
  max_retries?: number;
  error_budget?: ErrorBudgetStrategy;
  brand_style?: BrandStyle;
}

export interface Invariant {
  name: string;
  description: string;
  chain: ChainStep[];
  protected_functions: string[];
  settings?: Settings;
}

export interface VerifyLoopSpec {
  version: string;
  invariants: Invariant[];
}
