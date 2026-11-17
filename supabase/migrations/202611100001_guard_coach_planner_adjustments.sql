-- Coach adjustments can only transition through their confirmed conversation.
create or replace function public.guard_coach_adjustment_update()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  if auth.uid() is null then
    return new;
  end if;

  if old.source <> 'coach' then
    if new.source = 'coach' then
      raise exception 'Coach adjustment provenance cannot change' using errcode = '42501';
    end if;
    return new;
  end if;

  if row(new.source, new.id, new.user_id, new.adjustment_kind, new.target_id,
         new.target_type, new.workout_plan_id, new.diet_plan_id, new.requested_change,
         new.before_snapshot, new.after_snapshot, new.preview, new.expires_at, new.reversible)
     is distinct from
     row(old.source, old.id, old.user_id, old.adjustment_kind, old.target_id,
         old.target_type, old.workout_plan_id, old.diet_plan_id, old.requested_change,
         old.before_snapshot, old.after_snapshot, old.preview, old.expires_at, old.reversible) then
    raise exception 'Coach adjustment provenance cannot change' using errcode = '42501';
  end if;

  -- The foreign key may clear the link when its conversation is deleted.
  if new.conversation_id is distinct from old.conversation_id
     and (new.conversation_id is not null or exists (
       select 1 from public.coach_conversations where id = old.conversation_id
     )) then
    raise exception 'Coach adjustment conversation cannot change' using errcode = '42501';
  end if;

  if row(new.status, new.confirmed_at, new.rejected_at, new.applied_at, new.reverted_at, new.applied_change)
     is distinct from
     row(old.status, old.confirmed_at, old.rejected_at, old.applied_at, old.reverted_at, old.applied_change)
     and current_setting('evolv.coach_adjustment', true) is distinct from old.id::text then
    raise exception 'Confirm the adjustment in its Coach conversation' using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger guard_coach_adjustment_update
before update on public.planner_adjustments
for each row execute function public.guard_coach_adjustment_update();

create or replace function public.mutate_coach_adjustment(
  p_adjustment_id uuid,
  p_conversation_id uuid,
  p_operation text,
  p_confirmed boolean
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_user_id uuid := auth.uid();
  v_adjustment public.planner_adjustments%rowtype;
  v_current_item jsonb;
  v_expected jsonb;
  v_plan_status public.plan_status;
  v_swap_weekday public.weekday;
  v_previous_scope text := current_setting('evolv.coach_adjustment', true);
begin
  if v_user_id is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;

  if p_confirmed is distinct from true
     or p_operation is null
     or p_operation not in ('apply', 'reject', 'revert') then
    raise exception 'Explicit confirmation is required' using errcode = '22023';
  end if;

  select * into v_adjustment
  from public.planner_adjustments
  where id = p_adjustment_id
    and user_id = v_user_id
    and conversation_id = p_conversation_id
    and source = 'coach'
  for update;

  if not found then
    raise exception 'Coach adjustment not found in this conversation' using errcode = 'P0002';
  end if;

  if p_operation = 'apply' then
    if v_adjustment.status <> 'pending' then
      raise exception 'Only pending adjustments can be applied' using errcode = '22023';
    end if;
    if v_adjustment.expires_at <= now() then
      raise exception 'Planner adjustment expired' using errcode = '40001';
    end if;
    v_expected := v_adjustment.before_snapshot;
  elsif p_operation = 'revert' then
    if v_adjustment.status <> 'applied' or v_adjustment.reverted_at is not null or not v_adjustment.reversible then
      raise exception 'Planner adjustment cannot be reverted' using errcode = '22023';
    end if;
    v_expected := v_adjustment.after_snapshot;
  end if;

  if p_operation <> 'reject' then
    case v_adjustment.adjustment_kind
      when 'replace_meal_item' then
        select dp.status into v_plan_status from public.diet_plans dp
        where dp.id = v_adjustment.diet_plan_id and dp.user_id = v_user_id
        for update;
        if not found or (p_operation = 'apply' and v_plan_status <> 'active') then
          raise exception 'Diet plan changed after preview' using errcode = '40001';
        end if;

        select to_jsonb(mi) into v_current_item
        from public.meal_items mi
        join public.meals m on m.id = mi.meal_id
        where mi.id = v_adjustment.target_id and m.diet_plan_id = v_adjustment.diet_plan_id
        for update of mi;
        if not found or not (v_current_item @> (v_expected - 'meal_item_id'))
           or (v_current_item -> 'substitutions') is distinct from (v_expected -> 'substitutions') then
          raise exception 'Meal item changed after preview or adjustment' using errcode = '40001';
        end if;
      when 'replace_exercise', 'move_workout_day' then
        select wp.status into v_plan_status from public.workout_plans wp
        where wp.id = v_adjustment.workout_plan_id and wp.user_id = v_user_id
        for update;
        if not found or (p_operation = 'apply' and v_plan_status <> 'active') then
          raise exception 'Workout plan changed after preview' using errcode = '40001';
        end if;

        if v_adjustment.adjustment_kind = 'replace_exercise' then
          perform 1 from public.workout_day_exercises wde
          join public.workout_days wd on wd.id = wde.workout_day_id
          where wde.id = v_adjustment.target_id and wd.workout_plan_id = v_adjustment.workout_plan_id
          for update of wde;
          if not found then
            raise exception 'Workout exercise changed after preview' using errcode = '40001';
          end if;
        else
          perform 1 from public.workout_days
          where workout_plan_id = v_adjustment.workout_plan_id
          order by id for update;
          if p_operation = 'revert' and v_expected ->> 'swap_day_id' is not null then
            select weekday into v_swap_weekday from public.workout_days
            where id = (v_expected ->> 'swap_day_id')::uuid
              and workout_plan_id = v_adjustment.workout_plan_id;
            if not found or v_swap_weekday::text is distinct from v_expected ->> 'swap_weekday' then
              raise exception 'Swap day changed after adjustment' using errcode = '40001';
            end if;
          end if;
        end if;
      when 'set_day_activity' then
        perform 1 from public.daily_activity_overrides
        where user_id = v_user_id
          and activity_date = (v_adjustment.after_snapshot ->> 'activity_date')::date
        for update;
      else
        raise exception 'Unsupported Coach adjustment' using errcode = '22023';
    end case;
  end if;

  perform set_config('evolv.coach_adjustment', p_adjustment_id::text, true);
  if p_operation = 'reject' then
    perform public.reject_planner_adjustment(p_adjustment_id);
  elsif p_operation = 'apply' then
    if v_adjustment.adjustment_kind = 'set_day_activity' then
      perform public.apply_day_activity_adjustment(p_adjustment_id);
    else
      perform public.apply_planner_adjustment(p_adjustment_id);
    end if;
  elsif v_adjustment.adjustment_kind = 'set_day_activity' then
    perform public.revert_day_activity_adjustment(p_adjustment_id);
  else
    perform public.revert_planner_adjustment(p_adjustment_id);
    if v_adjustment.adjustment_kind = 'replace_meal_item'
       and v_adjustment.before_snapshot ? 'substitution_group' then
      update public.meal_items
      set substitution_group = v_adjustment.before_snapshot ->> 'substitution_group'
      where id = v_adjustment.target_id;
    end if;
  end if;
  perform set_config('evolv.coach_adjustment', coalesce(v_previous_scope, ''), true);
  return p_adjustment_id;
end;
$$;

revoke all on function public.mutate_coach_adjustment(uuid, uuid, text, boolean) from public;
grant execute on function public.mutate_coach_adjustment(uuid, uuid, text, boolean) to authenticated;
