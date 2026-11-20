// Shape of structuredContent returned by the Python describe_csv tool.
export type Scalar = string | number | boolean | null;

export interface ColumnStats {
  name: string;
  dtype: string;
  missing: number;
  values: Record<string, Scalar>; // statistic -> value (count, mean, std, min, 25%, 50%, 75%, max, unique, top, freq)
}

export interface DescribeResult {
  name: string;
  shape: { rows: number; columns: number };
  statistics: string[];
  columns: ColumnStats[];
  preview: { columns: string[]; rows: Scalar[][] };
}
