export interface VerificationError {
  file: string;
  line: number;
  column?: number;
  invariant?: string;
  violation: string;
  hint?: string;
  guard_definition?: string;
  is_guard_related: boolean;
}

export interface VerificationResult {
  success: boolean;
  errors: VerificationError[];
  warnings: VerificationError[];
}
