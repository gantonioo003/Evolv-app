create or replace function public.revert_day_activity_adjustment(
  p_adjustment_id uuid
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_adjustment public.planner_adjustments%rowtype;
  v_current public.daily_activity_overrides%rowtype;
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  select *
  into v_adjustment
  from public.planner_adjustments
  where id = p_adjustment_id
    and user_id = v_user_id
  for update;

  if not found then
    raise exception 'Planner adjustment not found' using errcode = 'P0002';
  end if;
  if v_adjustment.adjustment_kind <> 'set_day_activity'
     or v_adjustment.status <> 'applied'
     or v_adjustment.reverted_at is not null
     or not v_adjustment.reversible then
    raise exception 'Day activity adjustment cannot be reverted' using errcode = '22023';
  end if;

  select *
  into v_current
  from public.daily_activity_overrides
  where user_id = v_user_id
    and activity_date = (v_adjustment.after_snapshot ->> 'activity_date')::date;

  if not found
     or v_current.activity_type <> v_adjustment.after_snapshot ->> 'activity_type'
     or v_current.intensity is distinct from nullif(v_adjustment.after_snapshot ->> 'intensity', '')
     or v_current.estimated_minutes is distinct from nullif(v_adjustment.after_snapshot ->> 'estimated_minutes', '')::integer
     or v_current.workout_day_id is distinct from nullif(v_adjustment.after_snapshot ->> 'workout_day_id', '')::uuid
     or v_current.nutrition_day_type <> v_adjustment.after_snapshot ->> 'nutrition_day_type'
     or v_current.note is distinct from nullif(v_adjustment.after_snapshot ->> 'note', '') then
    raise exception 'Day activity changed after adjustment' using errcode = '40001';
  end if;

  if coalesce((v_adjustment.before_snapshot ->> 'existed')::boolean, false) then
    update public.daily_activity_overrides
    set
      activity_type = v_adjustment.before_snapshot ->> 'activity_type',
      intensity = nullif(v_adjustment.before_snapshot ->> 'intensity', ''),
      estimated_minutes = nullif(v_adjustment.before_snapshot ->> 'estimated_minutes', '')::integer,
      workout_day_id = nullif(v_adjustment.before_snapshot ->> 'workout_day_id', '')::uuid,
      nutrition_day_type = v_adjustment.before_snapshot ->> 'nutrition_day_type',
      source = coalesce(v_adjustment.before_snapshot ->> 'source', 'manual'),
      note = nullif(v_adjustment.before_snapshot ->> 'note', '')
    where id = v_current.id;
  else
    delete from public.daily_activity_overrides
    where id = v_current.id;
  end if;

  update public.planner_adjustments
  set reverted_at = now(), updated_at = now()
  where id = p_adjustment_id;

  return p_adjustment_id;
end;
$$;

revoke all on function public.revert_day_activity_adjustment(uuid) from public;
grant execute on function public.revert_day_activity_adjustment(uuid) to authenticated;
