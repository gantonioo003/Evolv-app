// Test-only Supabase fluent adapter backed by embedded PostgreSQL.
import { PGlite } from '@electric-sql/pglite';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
export async function coachDatabase({ product = false } = {}) {
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
      'grant usage on schema public,auth to authenticated,anon;',
  );
  if (product) {
    const migrations = resolve('../supabase/migrations');
    for (const name of readdirSync(migrations).sort()) {
      if (!name.endsWith('.sql') || name.startsWith('202609300002')) continue;
      await db.exec(
        readFileSync(resolve(migrations, name), 'utf8').replace(
          'create extension if not exists pgcrypto;',
          '',
        ),
      );
    }
  } else {
    await db.exec(
      enumSql + table('coach_conversations') + table('coach_messages'),
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
  }
  const supabase = {
    forUser: (user: string) => ({
      from: (table: string) => new Query(db, user, table),
      rpc: async (name: string, args: Record<string, unknown>) => {
        const allowed: Record<string, string[]> = {
          get_daily_activity_context: ['p_activity_date'],
          apply_planner_adjustment: ['p_adjustment_id'],
          reject_planner_adjustment: ['p_adjustment_id'],
          revert_planner_adjustment: ['p_adjustment_id'],
          apply_day_activity_adjustment: ['p_adjustment_id'],
          revert_day_activity_adjustment: ['p_adjustment_id'],
          mutate_coach_adjustment: [
            'p_adjustment_id',
            'p_conversation_id',
            'p_operation',
            'p_confirmed',
          ],
        };
        const keys = allowed[name];
        if (!keys) throw new Error('Unexpected fixture RPC');
        try {
          return await asUser(db, user, async (tx) => {
            const result = await tx.query<{ context: unknown }>(
              'select public.' +
                ident(name) +
                '(' +
                keys.map((_, i) => '$' + (i + 1)).join(',') +
                ') as context',
              keys.map((key) => args[key]),
            );
            return { data: result.rows[0]?.context, error: null };
          });
        } catch (error) {
          return { data: null, error };
        }
      },
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
async function asUser<T>(
  db: PGlite,
  user: string,
  run: (tx: Pick<PGlite, 'query' | 'exec'>) => Promise<T>,
) {
  return db.transaction(async (tx) => {
    await tx.query("select set_config('request.jwt.claim.sub',$1,true)", [
      user,
    ]);
    await tx.exec('set local role authenticated');
    return run(tx);
  });
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
  private columns = '*';
  private countOnly = false;
  select(cols = '*', options?: { head?: boolean }) {
    this.columns = cols;
    this.countOnly = Boolean(options?.head);
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
  neq(field: string, value: unknown) {
    this.filters.push({ field, op: '<>', value });
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
          (f.field === 'workout_days.workout_plan_id' &&
          this.table === 'workout_day_exercises'
            ? '(select wd.workout_plan_id from workout_days wd where wd.id = workout_day_exercises.workout_day_id)'
            : f.field === 'meals.diet_plan_id' && this.table === 'meal_items'
              ? '(select m.diet_plan_id from meals m where m.id = meal_items.meal_id)'
              : ident(f.field)) +
          (f.op === 'in'
            ? ' in (' + (f.value as unknown[]).map(bind).join(',') + ')'
            : ' ' +
              f.op +
              ' ' +
              bind(f.value) +
              (f.op === '@>' ? '::jsonb' : '')),
      )
      .join(' and ');
    let projection = '*';
    if (
      this.table === 'workout_plans' &&
      this.columns.includes('workout_days (')
    ) {
      projection += `, (select coalesce(jsonb_agg(to_jsonb(wd) || jsonb_build_object('workout_day_exercises',
        (select coalesce(jsonb_agg(to_jsonb(wde) || jsonb_build_object('exercises',
          (select to_jsonb(e) from exercises e where e.id = wde.exercise_id))), '[]'::jsonb)
          from workout_day_exercises wde where wde.workout_day_id = wd.id))), '[]'::jsonb)
        from workout_days wd where wd.workout_plan_id = workout_plans.id) as workout_days`;
    }
    if (this.table === 'diet_plans' && this.columns.includes('meals (')) {
      projection += `, (select coalesce(jsonb_agg(to_jsonb(m) || jsonb_build_object('meal_items',
        (select coalesce(jsonb_agg(to_jsonb(mi) || jsonb_build_object('foods',
          (select to_jsonb(f) from foods f where f.id = mi.food_id))), '[]'::jsonb)
          from meal_items mi where mi.meal_id = m.id))), '[]'::jsonb)
        from meals m where m.diet_plan_id = diet_plans.id) as meals`;
    }
    if (this.table === 'exercise_logs' && this.columns.includes('exercises')) {
      projection +=
        ", (select jsonb_build_object('name', e.name) from exercises e where e.id = exercise_logs.exercise_id) as exercises";
    }
    if (
      this.table === 'workout_day_exercises' &&
      this.columns.includes('exercises (')
    ) {
      projection +=
        ', (select to_jsonb(e) from exercises e where e.id = workout_day_exercises.exercise_id) as exercises';
    }
    let sql = 'select ' + projection + ' from public.' + ident(this.table);
    if (this.mode === 'insert') {
      const keys = Object.keys(this.rows[0]!).filter(
        (key) => this.rows[0]![key] !== undefined,
      );
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
      const jsonQuery =
        this.mode === 'select'
          ? 'select to_jsonb(row) as payload from (' + sql + ') row'
          : 'with modified as (' +
            sql +
            ') select to_jsonb(modified) as payload from modified';
      const rows = await asUser(this.db, this.user, async (tx) =>
        (await tx.query<{ payload: unknown }>(jsonQuery, params)).rows.map(
          (row) => row.payload,
        ),
      );
      if (this.countOnly)
        return { data: null, error: null, count: rows.length };
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
