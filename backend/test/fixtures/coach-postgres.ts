// Test-only Supabase fluent adapter backed by embedded PostgreSQL.
import { PGlite } from '@electric-sql/pglite';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
export async function coachDatabase() {
  const db = new PGlite();
  const source = readFileSync(
    resolve('../supabase/migrations/202609150001_initial_schema.sql'),
    'utf8',
  );
  const table = (name: string) =>
    source.match(
      new RegExp('create table public\\.' + name + ' \\([\\s\\S]*?\\n\\);'),
    )![0];
  const enumSql = source.match(
    /create type public\.coach_message_role as enum \([\s\S]*?\);/,
  )![0];
  await db.exec(
    'create schema auth;create table auth.users(id uuid primary key);create role authenticated;create role anon;' +
      "create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;" +
      enumSql +
      table('coach_conversations') +
      table('coach_messages'),
  );
  const policies = source.slice(
    source.indexOf(
      'create policy "Users can manage their own coach conversations"',
    ),
    source.indexOf('create policy "Users can manage their own coach memory"'),
  );
  await db.exec(
    'alter table public.coach_conversations enable row level security;alter table public.coach_messages enable row level security;' +
      policies +
      'grant usage on schema public,auth to authenticated,anon;grant all on public.coach_conversations,public.coach_messages to authenticated;' +
      'grant select on public.coach_conversations,public.coach_messages to anon;',
  );
  await db.exec(
    readFileSync(
      resolve(
        '../supabase/migrations/202609190004_fix_owned_reference_trigger.sql',
      ),
      'utf8',
    ),
  );
  const adjustmentEnum = source.match(
    /create type public\.adjustment_status as enum \([\s\S]*?\);/,
  )![0];
  const adjustmentPolicy = source.match(
    /create policy "Users can manage their own planner adjustments"[\s\S]*?;/,
  )![0];
  await db.exec(
    adjustmentEnum +
      table('planner_adjustments') +
      "alter table public.planner_adjustments add column source text default 'manual';" +
      'alter table public.planner_adjustments enable row level security;' +
      adjustmentPolicy +
      'grant all on public.planner_adjustments to authenticated;',
  );
  await db.exec(
    'create trigger coach_owned before insert or update on public.coach_messages for each row execute function public.enforce_owned_reference();',
  );
  const supabase = {
    forUser: (user: string) => ({
      from: (table: string) => new Query(db, user, table),
    }),
  };
  return {
    db,
    supabase,
    async user(id: string) {
      await db.query('insert into auth.users(id) values ($1)', [id]);
    },
  };
}
class Query {
  private mode = 'select';
  private rows: Record<string, unknown>[] = [];
  private filters: { field: string; op: string; value: unknown }[] = [];
  private ordering: string[] = [];
  private take?: number;
  private skip = 0;
  private cardinality = 'many';
  private ignore = false;
  constructor(
    private db: PGlite,
    private user: string,
    private table: string,
  ) {}
  select(_cols = '*') {
    return this;
  }
  insert(rows: Record<string, unknown> | Record<string, unknown>[]) {
    this.mode = 'insert';
    this.rows = Array.isArray(rows) ? rows : [rows];
    return this;
  }
  upsert(rows: Record<string, unknown>[], _options: unknown) {
    this.ignore = true;
    return this.insert(rows);
  }
  update(row: Record<string, unknown>) {
    this.mode = 'update';
    this.rows = [row];
    return this;
  }
  delete() {
    this.mode = 'delete';
    return this;
  }
  eq(field: string, value: unknown) {
    this.filters.push({ field, op: '=', value });
    return this;
  }
  in(field: string, value: unknown[]) {
    this.filters.push({ field, op: 'in', value });
    return this;
  }
  contains(field: string, value: unknown) {
    this.filters.push({ field, op: '@>', value });
    return this;
  }
  order(field: string, options = { ascending: true }) {
    this.ordering.push(ident(field) + (options.ascending ? ' asc' : ' desc'));
    return this;
  }
  limit(n: number) {
    this.take = n;
    return this;
  }
  range(a: number, b: number) {
    this.skip = a;
    this.take = b - a + 1;
    return this;
  }
  single() {
    this.cardinality = 'one';
    return this;
  }
  maybeSingle() {
    this.cardinality = 'optional';
    return this;
  }
  // oxlint-disable-next-line unicorn/no-thenable -- Matches the Supabase query-builder contract in tests.
  then<T>(
    resolve: (value: unknown) => T,
    reject?: (reason: unknown) => unknown,
  ) {
    return this.run().then(resolve, reject);
  }
  private async run() {
    const params: unknown[] = [];
    const bind = (v: unknown) => {
      params.push(v !== null && typeof v === 'object' ? JSON.stringify(v) : v);
      return '$' + params.length;
    };
    const where = this.filters
      .map(
        (f) =>
          ident(f.field) +
          (f.op === 'in'
            ? ' in (' + (f.value as unknown[]).map(bind).join(',') + ')'
            : ' ' +
              f.op +
              ' ' +
              bind(f.value) +
              (f.op === '@>' ? '::jsonb' : '')),
      )
      .join(' and ');
    let sql = 'select * from public.' + ident(this.table);
    if (this.mode === 'insert') {
      const keys = Object.keys(this.rows[0]!);
      sql =
        'insert into public.' +
        ident(this.table) +
        ' (' +
        keys.map(ident).join(',') +
        ') values ' +
        this.rows
          .map((r) => '(' + keys.map((k) => bind(r[k])).join(',') + ')')
          .join(',') +
        (this.ignore ? ' on conflict(id) do nothing' : '');
    } else if (this.mode === 'update') {
      sql =
        'update public.' +
        ident(this.table) +
        ' set ' +
        Object.entries(this.rows[0]!)
          .map(([k, v]) => ident(k) + '=' + bind(v))
          .join(',');
    } else if (this.mode === 'delete')
      sql = 'delete from public.' + ident(this.table);
    if (where) sql += ' where ' + where;
    if (this.mode === 'select') {
      if (this.ordering.length) sql += ' order by ' + this.ordering.join(',');
      if (this.take !== undefined)
        sql += ' limit ' + Number(this.take) + ' offset ' + Number(this.skip);
    } else sql += ' returning *';
    try {
      const rows = await this.db.transaction(async (tx) => {
        await tx.query("select set_config('request.jwt.claim.sub',$1,true)", [
          this.user,
        ]);
        await tx.exec('set local role authenticated');
        return (await tx.query(sql, params)).rows;
      });
      if (
        (this.cardinality === 'one' && rows.length !== 1) ||
        (this.cardinality === 'optional' && rows.length > 1)
      )
        return { data: null, error: { code: 'PGRST116' } };
      return {
        data: this.cardinality === 'many' ? rows : (rows[0] ?? null),
        error: null,
      };
    } catch (error) {
      return { data: null, error };
    }
  }
}
function ident(s: string) {
  if (!/^[a-z_]+$/.test(s)) throw Error('Invalid fixture identifier');
  return '"' + s + '"';
}
