'use client';

import { useCallback, useMemo, useTransition } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const KPI_OPTIONS = [
  { value: 'rto_rate', label: 'RTO Rate' },
  { value: 'sla_breach_pct', label: 'SLA Breach %' },
  { value: 'cod_delay_pct', label: 'COD Delay %' },
];

export function GlobalFilterBar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();

  const params = useMemo(() => new URLSearchParams(searchParams.toString()), [searchParams]);

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params);
      if (value && value.length) {
        next.set(key, value);
      } else {
        next.delete(key);
      }
      startTransition(() => {
        router.replace(`${pathname}?${next.toString()}`, { scroll: false });
      });
    },
    [params, pathname, router, startTransition],
  );

  const handleInputChange = useCallback(
    (key: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
      setParam(key, event.target.value);
    },
    [setParam],
  );

  const current = useMemo(
    () => ({
      run_id: params.get('run_id') ?? '',
      city: params.get('city') ?? '',
      carrier: params.get('carrier') ?? '',
      date_from: params.get('date_from') ?? '',
      date_to: params.get('date_to') ?? '',
      kpi: params.get('kpi') ?? KPI_OPTIONS[0].value,
    }),
    [params],
  );

  const resetFilters = useCallback(() => {
    startTransition(() => {
      router.replace(pathname, { scroll: false });
    });
  }, [pathname, router, startTransition]);

  return (
    <section className="border-b bg-background/95 px-6 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/75">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex min-w-[200px] flex-col gap-1">
          <Label htmlFor="run-id">Run ID</Label>
          <Input
            id="run-id"
            placeholder="fastcoo-latest"
            value={current.run_id}
            onChange={handleInputChange('run_id')}
            disabled={pending}
          />
        </div>
        <div className="flex min-w-[160px] flex-col gap-1">
          <Label htmlFor="city">City</Label>
          <Input id="city" value={current.city} onChange={handleInputChange('city')} disabled={pending} />
        </div>
        <div className="flex min-w-[160px] flex-col gap-1">
          <Label htmlFor="carrier">Carrier</Label>
          <Input id="carrier" value={current.carrier} onChange={handleInputChange('carrier')} disabled={pending} />
        </div>
        <div className="flex min-w-[160px] flex-col gap-1">
          <Label htmlFor="date-from">Date From</Label>
          <Input
            id="date-from"
            type="date"
            value={current.date_from}
            onChange={handleInputChange('date_from')}
            disabled={pending}
          />
        </div>
        <div className="flex min-w-[160px] flex-col gap-1">
          <Label htmlFor="date-to">Date To</Label>
          <Input
            id="date-to"
            type="date"
            value={current.date_to}
            onChange={handleInputChange('date_to')}
            disabled={pending}
          />
        </div>
        <div className="flex min-w-[160px] flex-col gap-1">
          <Label>KPI</Label>
          <Select
            value={current.kpi}
            onValueChange={(value) => {
              setParam('kpi', value);
            }}
            disabled={pending}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select KPI" />
            </SelectTrigger>
            <SelectContent>
              {KPI_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" onClick={resetFilters} disabled={pending}>
          Reset
        </Button>
      </div>
    </section>
  );
}
