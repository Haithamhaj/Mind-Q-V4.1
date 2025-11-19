'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import type { ColDef } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';

type TableResponse = {
  columns: { field: string; type: string }[];
  rows: Record<string, unknown>[];
};

const MAX_LIMIT = 10000;

export function AnalystGrid({ runId }: { runId: string }) {
  const searchParams = useSearchParams();
  const [payload, setPayload] = useState<TableResponse>({ columns: [], rows: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gridRef = useRef<AgGridReact<Record<string, unknown>>>(null);
  const [ready, setReady] = useState(false);

  const queryFilters = useMemo(() => {
    const limitCandidate = Number(searchParams.get('limit') ?? '1000');
    const normalizedLimit = Number.isFinite(limitCandidate) ? limitCandidate : 1000;
    return {
      city: searchParams.get('city') ?? null,
      carrier: searchParams.get('carrier') ?? null,
      limit: Math.min(Math.max(1, normalizedLimit), MAX_LIMIT),
    };
  }, [searchParams]);

  const fetchRows = useCallback(() => {
    if (!runId) {
      setPayload({ columns: [], rows: [] });
      return;
    }
    const params = new URLSearchParams({ run_id: runId, limit: String(queryFilters.limit || 1000) });
    if (queryFilters.city) params.set('city', queryFilters.city);
    if (queryFilters.carrier) params.set('carrier', queryFilters.carrier);
    setLoading(true);
    setError(null);
    fetch(`/api/v2/bi/table?${params.toString()}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load table (${response.status})`);
        }
        return response.json();
      })
      .then((data: TableResponse) => {
        setPayload(data);
      })
      .catch((err) => {
        setError(err.message);
        setPayload({ columns: [], rows: [] });
      })
      .finally(() => setLoading(false));
  }, [runId, queryFilters.city, queryFilters.carrier, queryFilters.limit]);

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  useEffect(() => {
    if (!ready) return;
    const api = gridRef.current?.api;
    if (!api) return;
    const filterModel: Record<string, unknown> = {};
    if (queryFilters.city) {
      filterModel.city = { type: 'equals', filter: queryFilters.city };
    }
    if (queryFilters.carrier) {
      filterModel.carrier = { type: 'equals', filter: queryFilters.carrier };
    }
    api.setFilterModel(filterModel);
    api.onFilterChanged();
  }, [queryFilters.city, queryFilters.carrier, ready]);

  const columnDefs: ColDef[] = useMemo(
    () =>
      payload.columns.map((column) => ({
        field: column.field,
        sortable: true,
        filter: column.type === 'number' ? 'agNumberColumnFilter' : 'agTextColumnFilter',
        resizable: true,
        flex: 1,
        minWidth: 120,
      })),
    [payload.columns],
  );

  if (!runId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Analyst Grid</CardTitle>
          <CardDescription>Provide a run_id to inspect raw rows.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Analyst Grid</CardTitle>
        <CardDescription>URL-driven AG Grid for analyst workflows.</CardDescription>
      </CardHeader>
      <CardContent>
        {loading && <p className="text-sm text-muted-foreground">Loading data…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && payload.rows.length === 0 && (
          <p className="text-sm text-muted-foreground">No rows found for the current filters.</p>
        )}
        <div className="ag-theme-quartz mt-4 w-full" style={{ height: 500 }}>
          <AgGridReact
            ref={gridRef}
            rowData={payload.rows}
            columnDefs={columnDefs}
            onGridReady={() => setReady(true)}
            suppressRowClickSelection
            animateRows
            pagination
            paginationPageSize={Math.min(queryFilters.limit || 1000, MAX_LIMIT)}
          />
        </div>
      </CardContent>
    </Card>
  );
}
